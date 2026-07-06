import { Button, Card } from '../../ui/components';
import { puedeIrAnterior, puedeIrSiguiente } from '../ExamenLogic';
import { soportaFullscreen, MENSAJE_LIMITE_FULLSCREEN } from '../../proctoring/fullscreenLockdown';
import type { ExamenRendicion } from '../../lib/examTakingApi';

interface Props {
  preguntaActual: ExamenRendicion['preguntas'][number] | null | undefined;
  indiceActual: number;
  total: number;
  cargandoPreguntas: boolean;
  respuestas: Record<string, string>;
  onSeleccionarOpcion: (preguntaId: string, opcionId: string) => void;
  onAnterior: () => void;
  onSiguiente: () => void;
  onFinalizar: () => void;
}

export function ExamenPreguntaCard({
  preguntaActual, indiceActual, total, cargandoPreguntas,
  respuestas,
  onSeleccionarOpcion, onAnterior, onSiguiente, onFinalizar,
}: Props) {
  return (
    <Card className="space-y-md">
      {/* Enunciado (el progreso y el timer viven en la barra superior) */}
      <div className="border-b border-outline-variant/40 pb-md">
        {cargandoPreguntas && (
          <p className="text-body-md text-on-surface-variant">Cargando preguntas…</p>
        )}
        {!cargandoPreguntas && !preguntaActual && (
          <p className="text-body-md text-on-surface-variant">
            No hay preguntas disponibles para este examen.
          </p>
        )}
        {preguntaActual && (
          <h2 className="font-headline text-title-lg text-on-surface leading-snug">
            {preguntaActual.enunciado}
          </h2>
        )}
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
