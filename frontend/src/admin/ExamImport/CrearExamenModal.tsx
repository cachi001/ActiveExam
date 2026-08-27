/**
 * Modal para crear un examen desde el banco de preguntas.
 *
 * Flujo:
 *  1. Usuario elige una o varias comisiones (derivan la materia) y el título.
 *  2. El modal carga las categorías del banco de esa materia.
 *  3. Para cada categoría (y "Sin clasificar") el usuario ve un renglón POR
 *     TIPO de pregunta disponible (multichoice, truefalse, cloze…) y puede
 *     poner cuántas quiere sortear de cada uno. Chips arriba filtran por tipo.
 *  4. Submit → POST /exam-content/crear-desde-banco (con comision_ids: el
 *     examen queda scopeado a esas comisiones, no visible para las demás).
 *
 * c-78 E-06: con varias comisiones se crea UN EXAMEN POR COMISIÓN, replicado
 * (D12) — se sortea una sola vez y ese set exacto se copia a los N. Quedan
 * independientes entre sí, y el modal lo avisa ANTES de crear, no después.
 */

import { useEffect, useState } from 'react';
import { Icon, Button, LoadingSpinner } from '../../ui/components';
import { ComisionMultiSelect } from '../../ui/ComisionMultiSelect';
import { useToast } from '../../ui/toast';
import {
  listarCategorias,
  listarPreguntasBanco,
  crearDesdeBanco,
  type CategoriaPregunta,
} from '../../lib/apiAdmin/bancoPreguntasApi';

const TIPO_PREGUNTA_LABEL: Record<string, string> = {
  multichoice: 'Opción múltiple',
  truefalse: 'Verdadero / Falso',
  cloze: 'Cloze',
};

function tipoLabel(tipo: string): string {
  return TIPO_PREGUNTA_LABEL[tipo] ?? tipo;
}

const INPUT_CLASS =
  'rounded-lg border border-surface-300 px-3 py-2 text-label-md text-on-surface focus:border-primary focus:outline-none disabled:bg-surface-100 disabled:text-on-surface-variant disabled:cursor-not-allowed';

interface TramoSorteo {
  categoria_id: string | null;
  categoria_nombre: string;
  tipo: string;
  disponibles: number;
  cantidad: number;
}

interface Props {
  abierto: boolean;
  onCerrar: () => void;
  /** `examenesCreados` es 1 salvo que se haya replicado a varias comisiones. */
  onCreado: (
    examenId: string,
    /** Largo del examen: cuántas preguntas rinde cada alumno. */
    largoDelExamen: number,
    examenesCreados: number,
    /** Pool del que se sortea ese largo. */
    poolDelExamen: number,
  ) => void;
}

export function CrearExamenModal({ abierto, onCerrar, onCreado }: Props) {
  const toast = useToast();
  const [materiaId, setMateriaId] = useState('');
  const [comisionIds, setComisionIds] = useState<string[]>([]);
  // Los códigos van aparte para poder mostrar cómo va a quedar el título de cada
  // réplica sin volver a pedir las comisiones.
  const [comisionCodigos, setComisionCodigos] = useState<string[]>([]);
  const [titulo, setTitulo] = useState('');
  // Solo se escribe: el árbol de categorías lo renderiza el selector de tramos.
  const [, setCategorias] = useState<CategoriaPregunta[]>([]);
  const [tramos, setTramos] = useState<TramoSorteo[]>([]);
  const [tipoFiltro, setTipoFiltro] = useState<string | null>(null);
  const [cargandoCats, setCargandoCats] = useState(false);
  const [enviando, setEnviando] = useState(false);
  // Escala de calificación: 100/60 por default (nunca "sobre 10" en silencio),
  // pero editable — cada docente/materia puede pedir otra escala.
  const [notaMaxima, setNotaMaxima] = useState(100);
  const [notaAprobacion, setNotaAprobacion] = useState(60);
  // c-78 E-07: el sorteo por intento es el ÚNICO modo de armado. No se elige.
  const SORTEO_POR_INTENTO = true;
  const [borrador, setBorrador] = useState(false);

  // Al cambiar materia, cargar categorías + contar disponibles
  useEffect(() => {
    setTipoFiltro(null);
    if (!materiaId) {
      setCategorias([]);
      setTramos([]);
      return;
    }
    setCargandoCats(true);
    Promise.all([
      listarCategorias(materiaId),
      listarPreguntasBanco(materiaId, null), // sin clasificar
    ])
      .then(async ([cats, sinClasificar]) => {
        setCategorias(cats);

        // Agrupa las preguntas de una categoría por tipo: un renglón por
        // (categoría, tipo) — así se puede pedir "3 opción múltiple + 2 cloze
        // de Unidad 1" en vez de un total mezclado sin control del tipo.
        const porTipo = (
          categoriaId: string | null,
          nombre: string,
          preguntas: { tipo: string }[],
        ): TramoSorteo[] => {
          const conteos = new Map<string, number>();
          for (const p of preguntas) {
            conteos.set(p.tipo, (conteos.get(p.tipo) ?? 0) + 1);
          }
          return [...conteos.entries()].map(([tipo, disponibles]) => ({
            categoria_id: categoriaId,
            categoria_nombre: nombre,
            tipo,
            disponibles,
            cantidad: 0,
          }));
        };

        const tramosBase: TramoSorteo[] = [];

        // "Sin clasificar" primero
        tramosBase.push(...porTipo(null, 'Sin clasificar', sinClasificar));

        // Una por una para obtener conteos (no hay endpoint de count, usamos listar)
        const conConteos = await Promise.all(
          cats.map(async (c) => {
            const preguntas = await listarPreguntasBanco(materiaId, c.id);
            return porTipo(c.id, c.nombre, preguntas);
          }),
        );

        tramosBase.push(...conConteos.flat());
        setTramos(tramosBase);
      })
      .catch(() => toast.error('Error al cargar categorías'))
      .finally(() => setCargandoCats(false));
  }, [materiaId]);

  if (!abierto) return null;

  const setCantidad = (idx: number, val: number) => {
    setTramos((prev) =>
      prev.map((t, i) =>
        i === idx ? { ...t, cantidad: Math.max(0, Math.min(val, t.disponibles)) } : t,
      ),
    );
  };

  // Tipos presentes en el banco de esta materia, para los chips de filtro.
  const tiposDisponibles = [...new Set(tramos.map((t) => t.tipo))];
  const tramosVisibles = tipoFiltro ? tramos.filter((t) => t.tipo === tipoFiltro) : tramos;

  const tramosActivos = tramos.filter((t) => t.cantidad > 0);
  const totalPreguntas = tramosActivos.reduce((s, t) => s + t.cantidad, 0);

  // Cómo va a quedar el título de la primera réplica. El backend arma el mismo
  // sufijo (código de comisión entre paréntesis) y solo cuando hay más de una.
  const tituloEjemplo = `${titulo.trim() || 'Título del examen'} (${comisionCodigos[0] ?? '…'})`;

  // c-78 E-07 (15.4): con sorteo por intento el examen se lleva el pool ENTERO de
  // cada tramo que tenga cantidad > 0, no solo las que se sortean.
  const poolDelExamen = tramosActivos.reduce((s, t) => s + t.disponibles, 0);

  // Cuántas preguntas comparten dos alumnos, en promedio: largo² / pool. Es la
  // cuenta que decide si el sorteo sirve de algo — con un pool apenas más grande
  // que el examen, dos alumnos rinden casi lo mismo igual.
  const repeticionEstimada =
    totalPreguntas > 0 && poolDelExamen > 0
      ? Math.round((totalPreguntas * totalPreguntas) / poolDelExamen)
      : null;
  const proporcion = repeticionEstimada !== null && totalPreguntas > 0
    ? repeticionEstimada / totalPreguntas
    : 0;
  const consejoDeRepeticion =
    proporcion >= 0.6
      ? 'Es mucho: para que se note, cargá más preguntas al banco o hacé el examen más corto.'
      : proporcion >= 0.3
        ? 'Se puede mejorar cargando más preguntas al banco o acortando el examen.'
        : 'Buena variedad.';

  const puedeCrear =
    materiaId.trim() !== '' &&
    comisionIds.length > 0 &&
    titulo.trim() !== '' &&
    tramosActivos.length > 0 &&
    notaMaxima > 0 &&
    notaMaxima <= 100 &&
    notaAprobacion >= 0 &&
    notaAprobacion <= notaMaxima &&
    !enviando;

  const handleCrear = async () => {
    if (!puedeCrear) return;
    setEnviando(true);
    try {
      const result = await crearDesdeBanco({
        titulo: titulo.trim(),
        materia_id: materiaId,
        comision_ids: comisionIds,
        sorteo: tramosActivos.map((t) => ({
          categoria_id: t.categoria_id,
          cantidad: t.cantidad,
          tipos: [t.tipo],
        })),
        nota_maxima: notaMaxima,
        nota_aprobacion: notaAprobacion,
        sorteo_por_intento: SORTEO_POR_INTENTO,
        borrador,
      });
      // El largo del examen (lo que rinde cada alumno) y el pool del que se sortea
      // son números distintos: `result.total_preguntas` es el POOL. Antes se avisaba
      // con el pool, así que quien pedía 10 de 30 leía "creado con 30 preguntas".
      onCreado(result.examen_id, totalPreguntas, result.examenes.length, poolDelExamen);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Error al crear examen');
    } finally {
      setEnviando(false);
    }
  };

  const handleClose = () => {
    if (enviando) return;
    setMateriaId('');
    setComisionIds([]);
    setComisionCodigos([]);
    setTitulo('');
    setTramos([]);
    setNotaMaxima(100);
    setNotaAprobacion(60);
    setBorrador(false);
    onCerrar();
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={handleClose} />
      <div className="relative z-10 w-full max-w-lg bg-white rounded-2xl shadow-xl flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center gap-3 px-6 pt-6 pb-4 border-b border-outline-variant/30">
          <div className="flex-1">
            <h2 className="text-title-md font-semibold text-on-surface">Crear examen</h2>
            <p className="text-label-md text-on-surface-variant">
              Sorteá preguntas del banco por categoría y tipo
            </p>
          </div>
          <button
            onClick={handleClose}
            className="p-1.5 rounded-lg hover:bg-surface-100 text-on-surface-variant"
          >
            <Icon name="close" className="text-[20px]" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {/* Título */}
          <label className="flex flex-col gap-1">
            <span className="text-label-sm font-medium text-on-surface-variant">
              Título del examen
            </span>
            <input
              type="text"
              value={titulo}
              placeholder="Ej: Parcial 1 — Programación 1"
              onChange={(e) => setTitulo(e.target.value)}
              className={INPUT_CLASS}
            />
          </label>

          {/* Comisiones (la materia queda embebida en cada opción) */}
          <div className="flex flex-col gap-1">
            <span className="text-label-sm font-medium text-on-surface-variant">
              Comisiones
            </span>
            <ComisionMultiSelect
              value={comisionIds}
              onChange={(ids, comisiones) => {
                setComisionIds(ids);
                setComisionCodigos(comisiones.map((c) => c.codigo));
                setMateriaId(comisiones[0]?.materia_id ?? '');
              }}
              disabled={enviando}
              className={INPUT_CLASS}
            />
          </div>
          {comisionIds.length <= 1 ? (
            <p className="text-label-sm text-on-surface-variant -mt-1">
              El examen queda visible solo para la comisión elegida. Podés agregar más
              de una y se crea un examen para cada una.
            </p>
          ) : (
            <div className="-mt-1 rounded-xl border border-outline-variant/40 bg-surface-100 px-3 py-2">
              <p className="text-label-sm text-on-surface">
                Se van a crear <strong>{comisionIds.length} exámenes</strong>, uno por
                comisión, con las mismas preguntas. Cada título lleva el código de su
                comisión: «{tituloEjemplo}».
              </p>
              <p className="text-label-sm text-on-surface-variant mt-1">
                Quedan independientes: si más adelante corregís algo, lo corregís en cada
                uno por separado. Si algo falla no se crea ninguno.
              </p>
            </div>
          )}

          {/* Escala de calificación */}
          <div className="flex gap-3">
            <label className="flex flex-col gap-1 flex-1">
              <span className="text-label-sm font-medium text-on-surface-variant">
                Nota máxima
              </span>
              <input
                type="number"
                min={1}
                max={100}
                value={notaMaxima}
                onChange={(e) =>
                  setNotaMaxima(Math.min(100, Math.max(0, parseFloat(e.target.value) || 0)))
                }
                className={INPUT_CLASS}
              />
            </label>
            <label className="flex flex-col gap-1 flex-1">
              <span className="text-label-sm font-medium text-on-surface-variant">
                Nota de aprobación
              </span>
              <input
                type="number"
                min={0}
                value={notaAprobacion}
                onChange={(e) => setNotaAprobacion(Math.max(0, parseFloat(e.target.value) || 0))}
                className={INPUT_CLASS}
              />
            </label>
          </div>
          {notaAprobacion > notaMaxima && (
            <p className="text-label-sm text-error -mt-2">
              La nota de aprobación no puede superar la nota máxima.
            </p>
          )}

          {/* Categorías */}
          {materiaId && (
            <div>
              <p className="text-label-sm font-medium text-on-surface-variant mb-2">
                Preguntas por categoría
              </p>

              {cargandoCats && (
                <LoadingSpinner size="sm" label="Cargando categorías…" />
              )}

              {!cargandoCats && tramos.length === 0 && (
                <p className="text-label-md text-on-surface-variant italic text-center py-4">
                  No hay preguntas en el banco para esta materia.
                </p>
              )}

              {!cargandoCats && tiposDisponibles.length > 1 && (
                <div className="flex flex-wrap gap-1.5 mb-2">
                  <button
                    type="button"
                    onClick={() => setTipoFiltro(null)}
                    className={`px-2.5 py-1 rounded-full text-label-sm border transition-colors ${
                      tipoFiltro === null
                        ? 'bg-primary text-white border-primary'
                        : 'border-surface-300 text-on-surface-variant hover:border-primary'
                    }`}
                  >
                    Todos
                  </button>
                  {tiposDisponibles.map((tipo) => (
                    <button
                      key={tipo}
                      type="button"
                      onClick={() => setTipoFiltro(tipo)}
                      className={`px-2.5 py-1 rounded-full text-label-sm border transition-colors ${
                        tipoFiltro === tipo
                          ? 'bg-primary text-white border-primary'
                          : 'border-surface-300 text-on-surface-variant hover:border-primary'
                      }`}
                    >
                      {tipoLabel(tipo)}
                    </button>
                  ))}
                </div>
              )}

              {!cargandoCats && tramos.length > 0 && (
                <div className="rounded-xl border border-outline-variant/40 overflow-hidden">
                  {tramosVisibles.map((t) => {
                    const idx = tramos.indexOf(t);
                    return (
                    <div
                      key={`${t.categoria_id ?? '__sin_clasificar__'}::${t.tipo}`}
                      className={`flex items-center gap-3 px-4 py-2 ${
                        idx < tramos.length - 1 ? 'border-b border-outline-variant/20' : ''
                      } ${t.cantidad > 0 ? 'bg-primary/5' : ''}`}
                    >
                      <Icon
                        name={t.categoria_id ? 'folder' : 'folder_off'}
                        className={`text-[16px] shrink-0 ${
                          t.cantidad > 0 ? 'text-primary' : 'text-on-surface-variant'
                        }`}
                      />
                      <div className="flex-1 min-w-0">
                        <div
                          className="text-label-md text-on-surface truncate"
                          title={t.categoria_nombre}
                        >
                          {t.categoria_nombre}
                        </div>
                        <div className="text-label-sm text-on-surface-variant">
                          {tipoLabel(t.tipo)}
                        </div>
                      </div>
                      <span className="text-label-sm text-on-surface-variant shrink-0">
                        {t.disponibles} disp.
                      </span>
                      <input
                        type="number"
                        min={0}
                        max={t.disponibles}
                        value={t.cantidad || ''}
                        placeholder="0"
                        onChange={(e) =>
                          setCantidad(idx, parseInt(e.target.value, 10) || 0)
                        }
                        className="w-16 rounded-lg border border-surface-300 px-2 py-1 text-label-md text-right text-on-surface focus:border-primary focus:outline-none"
                      />
                    </div>
                    );
                  })}
                </div>
              )}

              {totalPreguntas > 0 && (
                <p className="text-label-sm text-on-surface-variant mt-2 text-right">
                  Total:{' '}
                  <span className="text-on-surface font-semibold">{totalPreguntas} preguntas</span>
                </p>
              )}
            </div>
          )}

          {/* c-78 E-07: el sorteo por intento NO es opcional — todo examen reparte
              preguntas distintas a cada alumno. Antes era un checkbox que arrancaba
              apagado, así que el modo por defecto era el contrario al que se usa. */}
          {materiaId && (
            <div className="space-y-3 rounded-xl border border-outline-variant/40 p-3">
              <div className="flex items-start gap-2.5">
                <Icon name="shuffle" className="text-[18px] text-primary shrink-0 mt-0.5" />
                <span>
                  <span className="text-label-md text-on-surface">
                    Cada alumno recibe preguntas distintas
                  </span>
                  <span className="block text-label-sm text-on-surface-variant">
                    El sorteo se hace cuando cada alumno entra, no ahora. El examen se
                    lleva una copia de todas las preguntas elegibles, así que después
                    podés tocar el banco sin afectarlo.
                  </span>
                </span>
              </div>

              {totalPreguntas > 0 && (
                <div className="rounded-lg bg-surface-100 px-3 py-2">
                  <p className="text-label-sm text-on-surface">
                    Cada alumno rinde{' '}
                    <strong>
                      {totalPreguntas} {totalPreguntas === 1 ? 'pregunta' : 'preguntas'}
                    </strong>
                    , sorteadas de un pool de <strong>{poolDelExamen}</strong>.
                  </p>
                  <p className="text-label-sm text-on-surface-variant mt-1">
                    {repeticionEstimada === null
                      ? 'Elegí las cantidades para ver cuánto se van a repetir las preguntas entre alumnos.'
                      : `Dos alumnos van a compartir alrededor de ${repeticionEstimada} de ${totalPreguntas}. ${consejoDeRepeticion}`}
                  </p>
                </div>
              )}

              <label className="flex items-start gap-2.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={borrador}
                  onChange={(e) => setBorrador(e.target.checked)}
                  className="mt-0.5 shrink-0"
                />
                <span>
                  <span className="text-label-md text-on-surface">
                    Crearlo sin habilitar, para probarlo primero
                  </span>
                  <span className="block text-label-sm text-on-surface-variant">
                    No les aparece a los alumnos y no lo pueden rendir. Vos sí lo podés
                    rendir entero para ver cómo queda, incluso antes de la fecha de
                    apertura. Después lo habilitás desde el detalle del examen.
                  </span>
                </span>
              </label>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-outline-variant/30">
          <Button variant="ghost" onClick={handleClose} disabled={enviando}>
            Cancelar
          </Button>
          <Button onClick={handleCrear} disabled={!puedeCrear}>
            {enviando
              ? 'Creando…'
              : comisionIds.length > 1
                ? `Crear ${comisionIds.length} exámenes${totalPreguntas > 0 ? ` (${totalPreguntas} c/u)` : ''}`
                : `Crear examen${totalPreguntas > 0 ? ` (${totalPreguntas})` : ''}`}
          </Button>
        </div>
      </div>
    </div>
  );
}
