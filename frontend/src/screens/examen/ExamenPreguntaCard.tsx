import { Icon, Button, Card } from '../../ui/components';
import { puedeIrAnterior, puedeIrSiguiente } from '../ExamenLogic';
import { soportaFullscreen, MENSAJE_LIMITE_FULLSCREEN } from '../../proctoring/fullscreenLockdown';
import type { ExamenRendicion } from '../../lib/examTakingApi';
import { PreguntaCloze } from './PreguntaCloze';
import { renderTextoConCodigo } from './renderTextoConCodigo';

interface Props {
  preguntaActual: ExamenRendicion['preguntas'][number] | null | undefined;
  indiceActual: number;
  total: number;
  cargandoPreguntas: boolean;
  respuestas: Record<string, string>;
  /** Respuestas para preguntas cloze: preguntaId → { blankId → valor } */
  respuestasCloze: Record<string, Record<string, string>>;
  respondidas: Set<number>;
  segRestantes: number | null;
  tiempoLimiteMin: number | null | undefined;
  onSeleccionarOpcion: (preguntaId: string, opcionId: string) => void;
  onRespuestaCloze: (preguntaId: string, blankId: string, valor: string) => void;
  onAnterior: () => void;
  onSiguiente: () => void;
}

export function ExamenPreguntaCard({
  preguntaActual, indiceActual, total, cargandoPreguntas,
  respuestas, respuestasCloze, respondidas, segRestantes, tiempoLimiteMin,
  onSeleccionarOpcion, onRespuestaCloze, onAnterior, onSiguiente,
}: Props) {
  const mm = segRestantes !== null ? String(Math.floor(segRestantes / 60)).padStart(2, '0') : '00';
  const ss = segRestantes !== null ? String(segRestantes % 60).padStart(2, '0') : '00';
  const urgente = segRestantes !== null && segRestantes < 300;

  const esCloze = preguntaActual?.tipo === 'cloze';
  const blanks = preguntaActual?.blanks ?? [];
  const respuestasClozeActual = preguntaActual ? (respuestasCloze[preguntaActual.id] ?? {}) : {};

  return (
    <Card className="space-y-md">
      {/* Encabezado: pregunta actual + timer (dentro de la card) */}
      <div className="border-b border-outline-variant/40 pb-md">
        <div className="flex items-start justify-between gap-md flex-wrap">
          <div>
            <p className="text-title-md font-bold text-on-surface leading-tight">
              Pregunta {total > 0 ? indiceActual + 1 : '—'}
              <span className="font-normal text-on-surface-variant"> de {total}</span>
            </p>
            <p className="text-label-sm text-on-surface-variant mt-0.5">
              {respondidas.size} de {total} respondidas
            </p>
          </div>
          {segRestantes !== null ? (
            <span className={`inline-flex items-center gap-base px-md py-sm rounded-xl text-title-md font-bold tabular-nums shrink-0 ${
              urgente ? 'bg-error-container text-on-error-container' : 'bg-warning-container text-warning'
            }`}>
              <Icon name="timer" className="text-[20px]" /> {mm}:{ss}
            </span>
          ) : tiempoLimiteMin === null ? (
            <span className="inline-flex items-center gap-base px-md py-sm rounded-xl text-label-md font-medium bg-surface-container text-on-surface-variant shrink-0">
              <Icon name="timer_off" className="text-[18px]" /> Sin límite
            </span>
          ) : null}
        </div>
      </div>

      {/* Estado de carga / enunciado */}
      {cargandoPreguntas && (
        <p className="text-body-md text-on-surface-variant">Cargando preguntas…</p>
      )}
      {!cargandoPreguntas && !preguntaActual && (
        <p className="text-body-md text-on-surface-variant">
          No hay preguntas disponibles para este examen.
        </p>
      )}
      {preguntaActual && !esCloze && (
        <h2 className="text-body-md font-semibold text-on-surface leading-loose whitespace-pre-wrap rounded-xl border border-outline-variant/60 bg-surface-container-low p-md">
          {renderTextoConCodigo(preguntaActual.enunciado, preguntaActual.id)}
        </h2>
      )}

      {/* Opciones para preguntas estándar (multichoice / truefalse) */}
      {preguntaActual && !esCloze && (
        <div className="space-y-sm">
          {preguntaActual.opciones.map((op) => {
            const seleccionada = respuestas[preguntaActual.id] === op.id;
            return (
              <label key={op.id} className={`flex items-center gap-sm p-md rounded-xl border cursor-pointer transition-all ${
                seleccionada
                  ? 'border-primary bg-primary-fixed/40'
                  : 'border-outline-variant hover:border-primary/40 hover:bg-surface-container-low'
              }`}>
                <input
                  type="radio"
                  name={`q-${preguntaActual.id}`}
                  checked={seleccionada}
                  onChange={() => onSeleccionarOpcion(preguntaActual.id, op.id)}
                  className="w-4 h-4 accent-[#4241bc]"
                />
                <span className="text-body-md text-on-surface">{op.texto}</span>
              </label>
            );
          })}
        </div>
      )}

      {/* Pregunta cloze: huecos inline — el texto completo está embebido en PreguntaCloze */}
      {preguntaActual && esCloze && blanks.length > 0 && (
        <div className="space-y-md">
          <PreguntaCloze
            blanks={blanks}
            respuestas={respuestasClozeActual}
            onRespuesta={(blankId, valor) => onRespuestaCloze(preguntaActual.id, blankId, valor)}
          />
        </div>
      )}

      {/* Cloze sin blanks: fallback */}
      {preguntaActual && esCloze && blanks.length === 0 && (
        <div className="space-y-md">
          <h2 className="text-body-md font-semibold text-on-surface leading-loose whitespace-pre-wrap rounded-xl border border-outline-variant/60 bg-surface-container-low p-md">
            {renderTextoConCodigo(preguntaActual.enunciado, preguntaActual.id)}
          </h2>
          <p className="text-label-sm text-on-surface-variant italic">
            Esta pregunta no tiene huecos definidos.
          </p>
        </div>
      )}

      {/* Navegación entre preguntas (el botón de entregar vive en el panel de la derecha) */}
      <div className="flex items-center justify-between border-t border-outline-variant/40 pt-md gap-sm">
        {puedeIrAnterior(indiceActual) ? (
          <Button variant="outline" icon="arrow_back" onClick={onAnterior}>Anterior</Button>
        ) : (
          <div />
        )}
        {puedeIrSiguiente(indiceActual, total) ? (
          <Button icon="arrow_forward" onClick={onSiguiente}>Siguiente</Button>
        ) : (
          <div />
        )}
      </div>

      {!soportaFullscreen() && (
        <p className="text-label-sm text-on-surface-variant mt-base italic">{MENSAJE_LIMITE_FULLSCREEN}</p>
      )}
    </Card>
  );
}
