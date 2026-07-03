import { Icon, Button, Card } from '../../ui/components';
import { QuestionNavigator } from '../alumno/components/QuestionNavigator';
import { puedeIrAnterior, puedeIrSiguiente } from '../ExamenLogic';
import { soportaFullscreen, MENSAJE_LIMITE_FULLSCREEN } from '../../proctoring/fullscreenLockdown';
import type { ExamenRendicion } from '../../lib/examTakingApi';

interface Props {
  preguntaActual: ExamenRendicion['preguntas'][number] | undefined;
  indiceActual: number;
  total: number;
  cargandoPreguntas: boolean;
  respuestas: Record<string, string>;
  tiempoLimiteMin: number | null | undefined;
  segRestantes: number | null;
  respondidas: Set<number>;
  onSeleccionarOpcion: (preguntaId: string, opcionId: string) => void;
  onAnterior: () => void;
  onSiguiente: () => void;
  onFinalizar: () => void;
  onIr: (indice: number) => void;
}

export function ExamenPreguntaCard({
  preguntaActual, indiceActual, total, cargandoPreguntas,
  respuestas, tiempoLimiteMin, segRestantes, respondidas,
  onSeleccionarOpcion, onAnterior, onSiguiente, onFinalizar, onIr,
}: Props) {
  const mm = segRestantes !== null ? String(Math.floor(segRestantes / 60)).padStart(2, '0') : '00';
  const ss = segRestantes !== null ? String(segRestantes % 60).padStart(2, '0') : '00';

  return (
    <Card className="space-y-md">
      {/* Header: número de pregunta + timer */}
      <div className="flex items-start justify-between border-b border-outline-variant/40 pb-md gap-md">
        <div className="min-w-0 flex-1">
          {cargandoPreguntas && (
            <p className="text-body-md text-on-surface-variant">Cargando preguntas…</p>
          )}
          {!cargandoPreguntas && !preguntaActual && (
            <p className="text-body-md text-on-surface-variant">
              No hay preguntas disponibles para este examen.
            </p>
          )}
          {preguntaActual && (
            <>
              <p className="text-label-sm uppercase tracking-wide text-on-surface-variant">
                Pregunta {indiceActual + 1} de {total}
              </p>
              <h2 className="font-headline text-title-lg text-on-surface mt-base leading-snug">
                {preguntaActual.enunciado}
              </h2>
            </>
          )}
        </div>
        {segRestantes !== null ? (
          <span className={`inline-flex items-center gap-base px-sm py-base rounded-lg text-label-md font-bold shrink-0 ${segRestantes < 300 ? 'bg-error-container text-on-error-container' : 'bg-warning-container text-warning'}`}>
            <Icon name="timer" className="text-[18px]" /> {mm}:{ss}
          </span>
        ) : tiempoLimiteMin === null ? (
          <span className="inline-flex items-center gap-base px-sm py-base rounded-lg text-label-md font-bold bg-surface-container text-on-surface-variant shrink-0">
            <Icon name="timer_off" className="text-[18px]" /> Sin límite
          </span>
        ) : null}
      </div>

      {/* Opciones */}
      {preguntaActual && (
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

      {/* Navegador de preguntas — dentro de la card, separado de las opciones */}
      {total > 0 && (
        <div className="border-t border-outline-variant/30 pt-md space-y-xs">
          <p className="text-label-xs uppercase tracking-wide text-on-surface-variant">
            Navegación rápida
          </p>
          <QuestionNavigator
            total={total}
            indiceActual={indiceActual}
            respondidas={respondidas}
            onIr={onIr}
          />
        </div>
      )}

      {/* Botones de navegación */}
      <div className="flex items-center justify-between border-t border-outline-variant/40 pt-md gap-sm">
        {puedeIrAnterior(indiceActual) ? (
          <Button variant="outline" icon="arrow_back" onClick={onAnterior}>Anterior</Button>
        ) : (
          <div />
        )}
        <Button variant="outline" icon="check_circle" onClick={onFinalizar}>
          Terminar intento
        </Button>
        {puedeIrSiguiente(indiceActual, total) ? (
          <Button icon="arrow_forward" onClick={onSiguiente}>Siguiente</Button>
        ) : (
          <Button icon="check_circle" onClick={onFinalizar}>Finalizar y entregar</Button>
        )}
      </div>

      {!soportaFullscreen() && (
        <p className="text-label-sm text-on-surface-variant mt-base italic">{MENSAJE_LIMITE_FULLSCREEN}</p>
      )}
    </Card>
  );
}
