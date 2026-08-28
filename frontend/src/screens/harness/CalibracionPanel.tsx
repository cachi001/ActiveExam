/**
 * CalibracionPanel — medir cuán descentrada está la cámara, desde Test de detección.
 *
 * La calibración de mirada ya existía y corre al inicio del examen, pero ahí el
 * docente no la ve: es un overlay de tres segundos en la pantalla del alumno. Esta
 * pantalla es justamente donde se comprueba que el motor detecta bien ANTES de un
 * examen real, y no tenía forma de medir esto.
 *
 * Reusa `capturarBaselineGaze`, la misma función que usa el examen. No duplica la
 * captura: si mañana cambia cómo se calibra, cambia en un solo lugar.
 *
 * Presentacional salvo por la captura, que necesita el video y el motor.
 */
import { useState } from 'react';
import { Icon, Card, Button, SectionTitle, Badge } from '../../ui/components';
import { capturarBaselineGaze } from '../../proctoring/useExamProctoring';
import type { VisionEngine } from '../../vision/VisionEngine';
import {
  interpretarCalibracion,
  type ResultadoCalibracion,
  type NivelDesvio,
} from './calibracionCamara';

/** Los mismos que usa el examen, para medir en las mismas condiciones. */
const DURACION_MS = 3000;
const INTERVALO_MS = 100;

const TONO: Record<NivelDesvio, 'success' | 'warning' | 'error'> = {
  centrada: 'success',
  leve: 'warning',
  marcada: 'error',
};

const ETIQUETA: Record<NivelDesvio, string> = {
  centrada: 'Cámara centrada',
  leve: 'Algo corrida',
  marcada: 'Muy corrida',
};

const HACIA: Record<string, string> = {
  izquierda: 'hacia la izquierda',
  derecha: 'hacia la derecha',
  arriba: 'hacia arriba',
  abajo: 'hacia abajo',
};

interface Props {
  videoRef: React.RefObject<HTMLVideoElement>;
  engine: VisionEngine | null;
  /** La cámara tiene que estar encendida: sin frames no hay nada que medir. */
  camaraActiva: boolean;
  /** Se llama con el baseline capturado para que el pipeline lo use. */
  onCalibrado: (baseline: { x: number; y: number } | null) => void;
}

export default function CalibracionPanel({
  videoRef,
  engine,
  camaraActiva,
  onCalibrado,
}: Props) {
  const [resultado, setResultado] = useState<ResultadoCalibracion>({ estado: 'sin_calibrar' });

  const calibrar = async () => {
    if (!engine) return;
    setResultado({ estado: 'calibrando' });
    const baseline = await capturarBaselineGaze(
      videoRef,
      engine,
      DURACION_MS,
      INTERVALO_MS,
      () => false,
    );
    setResultado(interpretarCalibracion(baseline));
    onCalibrado(baseline);
  };

  const limpiar = () => {
    setResultado({ estado: 'sin_calibrar' });
    onCalibrado(null);
  };

  return (
    <Card className="space-y-md">
      <SectionTitle sub="Mide si la cámara está alineada con la pantalla. Es el mismo paso que corre el alumno antes de empezar el examen.">
        Calibración de cámara
      </SectionTitle>

      {!camaraActiva && (
        <div className="flex items-start gap-2 rounded-lg bg-surface-container px-3 py-2.5">
          <Icon name="videocam_off" className="text-[18px] shrink-0 mt-0.5 text-on-surface-variant" />
          <p className="text-label-md text-on-surface-variant">
            Encendé la cámara con «Probar» para poder calibrar.
          </p>
        </div>
      )}

      {/* Cómo ubicarse ANTES de medir. Sin esto la medición sale mal y no se sabe
          por qué: alguien que calibra de perfil, o con la cámara apuntando desde
          un costado, fija un baseline torcido y después el sistema mide toda la
          rendición contra ese punto equivocado. */}
      {camaraActiva && resultado.estado === 'sin_calibrar' && (
        <div className="rounded-lg border border-surface-200 px-md py-sm space-y-1.5">
          <p className="text-label-md text-on-surface">Antes de medir, acomodá el puesto:</p>
          <ul className="text-label-md text-on-surface-variant space-y-1">
            {/* El texto va envuelto en un span: dentro de un `li` flex, cada nodo
                suelto (el texto, el <strong>, el resto) sería un ítem de flex
                aparte y la frase se partía con huecos en el medio. */}
            <li className="flex items-start gap-2">
              <Icon name="check" className="text-[16px] shrink-0 mt-0.5 text-primary" />
              <span>
                La cámara tiene que estar <strong className="text-on-surface">enfrente</strong>, a
                la altura de los ojos, no a un costado ni apoyada abajo.
              </span>
            </li>
            <li className="flex items-start gap-2">
              <Icon name="check" className="text-[16px] shrink-0 mt-0.5 text-primary" />
              <span>Sentate de frente a la pantalla, con la cara entera dentro del cuadro.</span>
            </li>
            <li className="flex items-start gap-2">
              <Icon name="check" className="text-[16px] shrink-0 mt-0.5 text-primary" />
              <span>Con luz de frente, no con una ventana detrás.</span>
            </li>
          </ul>
        </div>
      )}

      {resultado.estado === 'calibrando' && (
        // `primary-fixed` es el token de fondo suave del design system. Con
        // `primary-container` (#4469eb, azul fuerte) el texto encima no se lee.
        <div className="flex items-start gap-3 rounded-lg bg-primary-fixed px-3 py-3">
          <Icon name="progress_activity" className="ae-spin text-primary text-[22px] shrink-0" />
          <div>
            <p className="text-label-md font-medium text-on-surface">
              Mirá al centro de la pantalla, de frente
            </p>
            <p className="text-label-sm text-on-surface-variant">
              Quedate mirando el centro unos segundos, sin mover la cabeza.
            </p>
          </div>
        </div>
      )}

      {resultado.estado === 'fallida' && (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-lg bg-error-container/40 px-3 py-2.5"
        >
          <Icon name="error" className="text-[18px] shrink-0 mt-0.5 text-error" fill />
          <p className="text-label-md text-on-surface">
            No se pudo medir: no se detectó una cara durante la medición. Ubicate de
            frente a la cámara, con la cara entera dentro del cuadro y luz de frente,
            y probá de nuevo.
          </p>
        </div>
      )}

      {resultado.estado === 'lista' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <Badge tone={TONO[resultado.nivel]} dot>
              {ETIQUETA[resultado.nivel]}
            </Badge>
            <span className="text-label-sm text-on-surface-variant">
              Desvío{' '}
              <strong className="text-on-surface font-semibold tabular-nums">
                {resultado.desvio.toFixed(3)}
              </strong>
              {resultado.direccion && <> · {HACIA[resultado.direccion]}</>}
            </span>
          </div>

          <p className="text-label-md text-on-surface-variant leading-relaxed">
            {resultado.consejo}
          </p>

          {/* El baseline crudo: es lo que se le pasa al motor, y verlo permite
              comparar dos equipos o dejarlo asentado en un acta. */}
          <p className="text-label-sm text-on-surface-variant font-mono">
            baseline x {resultado.baseline.x.toFixed(4)} · y {resultado.baseline.y.toFixed(4)}
          </p>
        </div>
      )}

      <div className="flex justify-end gap-sm pt-sm border-t border-outline-variant/40">
        {resultado.estado === 'lista' || resultado.estado === 'fallida' ? (
          <Button variant="ghost" size="sm" icon="restart_alt" onClick={limpiar}>
            Descartar
          </Button>
        ) : null}
        <Button
          variant="primary"
          size="sm"
          icon="visibility"
          onClick={() => void calibrar()}
          disabled={!camaraActiva || !engine || resultado.estado === 'calibrando'}
        >
          {resultado.estado === 'calibrando' ? 'Midiendo…' : 'Calibrar cámara'}
        </Button>
      </div>
    </Card>
  );
}
