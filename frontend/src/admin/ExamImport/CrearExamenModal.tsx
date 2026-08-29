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

import { useState } from 'react';
import {
  MINUTOS_LIMITE_POR_DEFECTO,
  aperturaSugerida,
  cierreSugerido,
  deInputLocalAIso,
  errorDeVentana,
} from './ventanaPorDefecto';
import { Icon, Button } from '../../ui/components';
import { ComisionMultiSelect } from '../../ui/ComisionMultiSelect';
import { ModalOverlay } from '../../ui/ModalOverlay';
import { useToast } from '../../ui/toast';
import { crearDesdeBanco } from '../../lib/apiAdmin/bancoPreguntasApi';
import { SelectorDeSorteo, type SorteoArmado } from './SelectorDeSorteo';



const INPUT_CLASS =
  'rounded-lg border border-surface-300 px-3 py-2 text-label-md font-normal text-on-surface focus:border-primary focus:outline-none disabled:bg-surface-100 disabled:text-on-surface-variant disabled:cursor-not-allowed';

/** Rótulo de campo: mismo cuerpo que el valor, en gris. */
const LABEL_CLASS = 'text-label-md font-medium text-on-surface-variant';

// El armado de tramos, los conteos por rama y la cuenta de repetición viven en
// `tramosDelBanco.ts`: es la parte que decide si el examen sortea de verdad y
// tiene sus propios tests.

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
  // Lo que armó el selector. `null` hasta que hay materia elegida.
  const [sorteo, setSorteo] = useState<SorteoArmado | null>(null);
  const [enviando, setEnviando] = useState(false);
  // Escala de calificación: 100/60 por default (nunca "sobre 10" en silencio),
  // pero editable — cada docente/materia puede pedir otra escala.
  const [notaMaxima, setNotaMaxima] = useState(100);
  const [notaAprobacion, setNotaAprobacion] = useState(60);
  // c-78 E-07: el sorteo por intento es el ÚNICO modo de armado. No se elige.
  const SORTEO_POR_INTENTO = true;
  const [borrador, setBorrador] = useState(false);
  // Ventana de rendición: OBLIGATORIA. Llega prellenada (ahora → +7 días) para
  // que ponerla sea un clic, pero el formulario no deja crear sin ella. Antes el
  // examen nacía sin fechas y al alumno le aparecía "Sin fecha de cierre".
  const [apertura, setApertura] = useState(() => aperturaSugerida());
  const [cierre, setCierre] = useState(() => cierreSugerido());
  const errorVentana = errorDeVentana(apertura, cierre);
  // Reloj del examen. Sin límite, la rendición vence recién en el cierre de la
  // ventana (una semana por defecto): la sesión de proctoring quedaría abierta
  // días, con la cámara prendida. Por defecto, una hora.
  const [tiempoLimite, setTiempoLimite] = useState(MINUTOS_LIMITE_POR_DEFECTO);


  if (!abierto) return null;

  // Cómo va a quedar el título de la primera réplica. El backend arma el mismo
  // sufijo (código de comisión entre paréntesis) y solo cuando hay más de una.
  const tituloEjemplo = `${titulo.trim() || 'Título del examen'} (${comisionCodigos[0] ?? '…'})`;

  const elegidas = sorteo?.largo ?? 0;
  const puedeCrear =
    materiaId.trim() !== '' &&
    comisionIds.length > 0 &&
    titulo.trim() !== '' &&
    Boolean(sorteo?.valido) &&
    notaMaxima > 0 &&
    notaMaxima <= 100 &&
    notaAprobacion >= 0 &&
    notaAprobacion <= notaMaxima &&
    errorVentana === null &&
    tiempoLimite > 0 &&
    !enviando;

  const handleCrear = async () => {
    if (!puedeCrear) return;
    setEnviando(true);
    try {
      const result = await crearDesdeBanco({
        pool_preguntas: sorteo?.pool_preguntas,
        titulo: titulo.trim(),
        materia_id: materiaId,
        comision_ids: comisionIds,
        sorteo: sorteo?.sorteo ?? [],
        nota_maxima: notaMaxima,
        nota_aprobacion: notaAprobacion,
        sorteo_por_intento: SORTEO_POR_INTENTO,
        apertura: deInputLocalAIso(apertura),
        cierre: deInputLocalAIso(cierre),
        tiempo_limite_min: tiempoLimite,
        borrador,
      });
      // El largo del examen (lo que rinde cada alumno) y el pool del que se sortea
      // son números distintos: `result.total_preguntas` es el POOL. Antes se avisaba
      // con el pool, así que quien pedía 10 de 30 leía "creado con 30 preguntas".
      onCreado(result.examen_id, elegidas, result.examenes.length, sorteo?.poolTotal ?? 0);
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
    setSorteo(null);
    setNotaMaxima(100);
    setNotaAprobacion(60);
    setBorrador(false);
    onCerrar();
  };

  return (
    <ModalOverlay etiqueta="Crear examen" onCerrar={handleClose}>
      <div className="relative w-full max-w-3xl bg-white rounded-2xl shadow-xl flex flex-col max-h-[90vh]">
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
            <span className={LABEL_CLASS}>Título del examen</span>
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
            <span className={LABEL_CLASS}>Comisiones</span>
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

          {/* Ventana de rendición — obligatoria (decisión del dueño). */}
          <div className="flex gap-3">
            <label className="flex flex-col gap-1 flex-1">
              <span className={LABEL_CLASS}>Inicio del examen</span>
              <input
                type="datetime-local"
                value={apertura}
                onChange={(e) => setApertura(e.target.value)}
                className={INPUT_CLASS}
              />
            </label>
            <label className="flex flex-col gap-1 flex-1">
              <span className={LABEL_CLASS}>Cierre del examen</span>
              <input
                type="datetime-local"
                value={cierre}
                onChange={(e) => setCierre(e.target.value)}
                className={INPUT_CLASS}
              />
            </label>
          </div>
          <label className="flex flex-col gap-1">
            <span className={LABEL_CLASS}>Tiempo para resolverlo (minutos)</span>
            <input
              type="number"
              min={1}
              value={tiempoLimite}
              onChange={(e) => setTiempoLimite(Math.max(0, parseInt(e.target.value, 10) || 0))}
              className={INPUT_CLASS}
            />
          </label>
          {errorVentana ? (
            <p className="text-label-sm text-error -mt-1">{errorVentana}</p>
          ) : (
            <p className="text-label-sm text-on-surface-variant -mt-1">
              Fuera de estas fechas el examen no se puede rendir, y cada alumno tiene{' '}
              {tiempoLimite} minutos desde que arranca. Podés cambiarlo después desde la
              configuración del examen.
            </p>
          )}

          {/* Escala de calificación */}
          <div className="flex gap-3">
            <label className="flex flex-col gap-1 flex-1">
              <span className={LABEL_CLASS}>
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
              <span className={LABEL_CLASS}>
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

          {/* El selector vive aparte: es la MISMA pantalla de armado que
              usa la edición del sorteo en el detalle del examen. */}
          {materiaId && (
            <SelectorDeSorteo materiaId={materiaId} onChange={setSorteo} />
          )}


          {/* c-78 E-07: el sorteo por intento NO es opcional — todo examen reparte
              preguntas distintas a cada alumno. Antes era un checkbox que arrancaba
              apagado, así que el modo por defecto era el contrario al que se usa. */}
          {materiaId && (
            <div className="space-y-3 rounded-xl border border-outline-variant/40 p-3">
              {/* Era un bloque del alto de media pantalla para decir algo que no se
                  decide acá: el sorteo por intento es el único modo de armado. */}
              <p className="flex items-center gap-1.5 text-label-sm text-on-surface-variant">
                <Icon name="shuffle" className="text-[16px] text-primary shrink-0" />
                El sorteo se hace cuando cada alumno entra, sobre una copia del banco.
              </p>

              {/* El detalle de la repetición lo muestra el propio selector; acá
                  alcanza con el resumen de lo que se va a crear. */}
              {elegidas > 0 && (
                <div className="rounded-lg bg-surface-100 px-3 py-2">
                  <p className="text-label-sm text-on-surface">
                    Cada alumno rinde{' '}
                    <strong>
                      {elegidas} {elegidas === 1 ? 'pregunta' : 'preguntas'}
                    </strong>
                    , sorteadas de un pool de <strong>{sorteo?.poolTotal ?? 0}</strong>.
                  </p>
                </div>
              )}

              <label className="flex items-start gap-2.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={borrador}
                  onChange={(e) => setBorrador(e.target.checked)}
                  className="accent-primary w-4 h-4 shrink-0 mt-0.5"
                />
                <span>
                  <span className="text-label-md text-on-surface">
                    Crearlo sin habilitar, para probarlo primero
                  </span>
                  <span className="block text-label-sm text-on-surface-variant">
                    {/* Antes prometía que el docente podía rendirlo entero, y la
                        guarda de inscripción se lo rechaza con 403: nunca está
                        inscripto como alumno de su propia comisión. */}
                    No les aparece a los alumnos y no lo pueden rendir. Vos podés
                    revisar las preguntas y la configuración, y habilitarlo desde el
                    detalle cuando esté listo. También se puede volver a esconder,
                    mientras no lo haya rendido nadie.
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
                ? `Crear ${comisionIds.length} exámenes${elegidas > 0 ? ` (${elegidas} c/u)` : ''}`
                : `Crear examen${elegidas > 0 ? ` (${elegidas})` : ''}`}
          </Button>
        </div>
      </div>
    </ModalOverlay>
  );
}
