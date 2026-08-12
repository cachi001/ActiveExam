/**
 * Modal para crear un examen desde el banco de preguntas.
 *
 * Flujo:
 *  1. Usuario elige comisión (deriva la materia) y título.
 *  2. El modal carga las categorías del banco de esa materia.
 *  3. Para cada categoría (y "Sin clasificar") el usuario ve un renglón POR
 *     TIPO de pregunta disponible (multichoice, truefalse, cloze…) y puede
 *     poner cuántas quiere sortear de cada uno. Chips arriba filtran por tipo.
 *  4. Submit → POST /exam-content/crear-desde-banco (con comision_id: el
 *     examen queda scopeado a esa comisión, no visible para las demás).
 */

import { useEffect, useState } from 'react';
import { Icon, Button, LoadingSpinner } from '../../ui/components';
import { ComisionSelect } from '../../ui/ComisionSelect';
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
  onCreado: (examenId: string, totalPreguntas: number) => void;
}

export function CrearExamenModal({ abierto, onCerrar, onCreado }: Props) {
  const toast = useToast();
  const [materiaId, setMateriaId] = useState('');
  const [comisionId, setComisionId] = useState('');
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

  const puedeCrear =
    materiaId.trim() !== '' &&
    comisionId.trim() !== '' &&
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
        comision_id: comisionId,
        sorteo: tramosActivos.map((t) => ({
          categoria_id: t.categoria_id,
          cantidad: t.cantidad,
          tipos: [t.tipo],
        })),
        nota_maxima: notaMaxima,
        nota_aprobacion: notaAprobacion,
      });
      onCreado(result.examen_id, result.total_preguntas);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Error al crear examen');
    } finally {
      setEnviando(false);
    }
  };

  const handleClose = () => {
    if (enviando) return;
    setMateriaId('');
    setComisionId('');
    setTitulo('');
    setTramos([]);
    setNotaMaxima(100);
    setNotaAprobacion(60);
    onCerrar();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40" onClick={handleClose} />
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

          {/* Comisión (la materia queda embebida en cada opción) */}
          <label className="flex flex-col gap-1">
            <span className="text-label-sm font-medium text-on-surface-variant">Comisión</span>
            <ComisionSelect
              value={comisionId}
              onChange={(id, comision) => {
                setComisionId(id);
                setMateriaId(comision?.materia_id ?? '');
              }}
              className={INPUT_CLASS}
            />
          </label>
          <p className="text-label-sm text-on-surface-variant -mt-2">
            El examen queda visible solo para la comisión elegida.
          </p>

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
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-outline-variant/30">
          <Button variant="ghost" onClick={handleClose} disabled={enviando}>
            Cancelar
          </Button>
          <Button onClick={handleCrear} disabled={!puedeCrear}>
            {enviando ? 'Creando…' : `Crear examen${totalPreguntas > 0 ? ` (${totalPreguntas})` : ''}`}
          </Button>
        </div>
      </div>
    </div>
  );
}
