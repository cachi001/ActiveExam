/**
 * Tarjeta de calibración de mirada. La usa la pantalla `Calibracion`, que es el
 * PASO 3 del ingreso (entre la verificación biométrica y la sala de espera).
 *
 * ## Por qué es un paso y no algo del examen
 *
 * La calibración (3 s mirando al centro) corría DENTRO de la rendición, con el
 * cronómetro ya andando y un cartel que no decía cómo había salido: le comía
 * tiempo al alumno y era una caja negra. Decisión del dueño (29/8/2026): es un
 * paso propio del wizard, con su resultado a la vista y su botón para repetirla.
 *
 * El baseline queda en `baselineGaze` y el examen lo toma de ahí sin recalibrar.
 *
 * ## Qué hace la calibración
 *
 * Mide hacia dónde mira el alumno cuando mira la pantalla, y usa eso como punto
 * cero. Sin ese cero, a alguien con la cámara al costado se le marcaría "mirada
 * desviada" por leer normalmente.
 *
 * ## Degradación
 *
 * Si la cámara o el motor de visión fallan, NO bloquea: el examen arranca con el
 * baseline por defecto y su propia calibración de respaldo. Perder la precisión
 * del detector es mucho menos grave que dejar a alguien sin rendir.
 */
import { useCallback, useEffect, useRef, useState, type RefObject } from 'react';

import { Icon, Button } from '../../ui/components';
import { loadRealEngine } from '../../vision/harnessEngineLoader';
import { capturarBaselineGaze } from '../../proctoring/useExamProctoring';
import {
  baselineGazeGuardado,
  guardarBaselineGaze,
  posicionDeLaCamara,
} from '../../proctoring/baselineGaze';

export type EstadoCalibracion = 'pendiente' | 'midiendo' | 'lista' | 'sin_camara';

/**
 * Duración de la medición. Eran 3 s heredados del overlay que corría dentro del
 * examen, donde interesaba estorbar lo menos posible. Como paso propio conviene
 * lo contrario: más muestras = un cero más estable, y al alumno le da tiempo de
 * acomodarse. Con cuenta regresiva a la vista, para que no se sienta apurado.
 */
const DURACION_MS = 6000;
const INTERVALO_MS = 200;
const SEGUNDOS = Math.round(DURACION_MS / 1000);

interface Props {
  videoRef: RefObject<HTMLVideoElement>;
  estado: EstadoCalibracion;
  onEstado: (e: EstadoCalibracion) => void;
}

export function CalibracionPaso({ videoRef, estado, onEstado }: Props) {
  // De qué lado quedó la cámara, según lo que se acaba de medir.
  const posicion = posicionDeLaCamara(baselineGazeGuardado());
  // La cámara queda PRENDIDA después de medir, para que el alumno se vea y pueda
  // acomodarla antes de recalibrar. Se libera al salir del paso: si siguiera
  // tomada, el `getUserMedia` del examen competiría con este stream.
  const streamRef = useRef<MediaStream | null>(null);
  const [restante, setRestante] = useState(SEGUNDOS);

  /** Enciende la cámara para que el alumno se vea. No mide nada. */
  const encenderCamara = useCallback(async (): Promise<MediaStream> => {
    if (streamRef.current) return streamRef.current;
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'user' },
      audio: false,
    });
    streamRef.current = stream;
    const video = videoRef.current;
    if (video) {
      video.srcObject = stream;
      await video.play().catch(() => {});
    }
    return stream;
  }, [videoRef]);

  const soltarCamara = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
  }, [videoRef]);

  useEffect(() => soltarCamara, [soltarCamara]);

  const calibrar = useCallback(async () => {
    onEstado('midiendo');
    setRestante(SEGUNDOS);
    // La cuenta regresiva corre en paralelo a la medición: sin nada a la vista,
    // 6 segundos quietos frente a la cámara se sienten como que se colgó.
    const tic = setInterval(() => setRestante((n) => Math.max(0, n - 1)), 1000);
    try {
      await encenderCamara();
      if (!videoRef.current) throw new Error('sin elemento de video');

      const engine = await loadRealEngine();
      const baseline = await capturarBaselineGaze(
        videoRef,
        engine,
        DURACION_MS,
        INTERVALO_MS,
        () => false,
      );
      guardarBaselineGaze(baseline);

      onEstado(baseline ? 'lista' : 'sin_camara');
    } catch {
      // Sin cámara / sin permiso / motor caído: no bloquea el examen.
      guardarBaselineGaze(null);
      soltarCamara();
      onEstado('sin_camara');
    } finally {
      clearInterval(tic);
    }
  }, [encenderCamara, onEstado, soltarCamara, videoRef]);

  // Cámara encendida al ENTRAR al paso, sin medir: el alumno se ve, se acomoda y
  // recién entonces calibra. Antes la pantalla mostraba un rectángulo negro
  // hasta que apretaba el botón.
  useEffect(() => {
    void encenderCamara().catch(() => onEstado('sin_camara'));
    // Solo al montar.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="rounded-2xl border border-outline-variant/50 bg-white p-lg space-y-md text-left">
      <div className="flex items-start gap-sm">
        <div
          className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${
            estado === 'lista'
              ? 'bg-success-container text-success'
              : estado === 'sin_camara'
                ? 'bg-warning-container text-warning'
                : 'bg-primary-fixed text-primary'
          }`}
        >
          <Icon
            name={
              estado === 'lista'
                ? 'check_circle'
                : estado === 'sin_camara'
                  ? 'error'
                  : 'visibility'
            }
            className="text-[20px]"
            fill
          />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-label-md font-semibold text-on-surface">
            Calibración de la mirada
          </p>

          {estado === 'midiendo' && (
            // Una sola línea: mientras mide tiene que estar mirando la pantalla,
            // no leyendo. El consejo de la cámara ya se dio en «pendiente».
            <p className="text-[13px] text-on-surface-variant mt-1">
              Mirá la pantalla donde vas a rendir, como si estuvieras leyendo.
            </p>
          )}

          {estado === 'lista' && (
            <>
              {/* Resultado CONCRETO. Antes decía "listo" y nada más, así que no
                  se notaba que hubiera medido algo. De qué lado quedó la cámara
                  es lo único del baseline que se puede leer en castellano, y es
                  justo lo que contesta "¿de qué me sirve calibrar?". */}
              <p className="text-[13px] text-on-surface-variant mt-1">
                <strong className="text-success">Listo.</strong>{' '}
                {posicion === 'centrada' ? (
                  <>Tu cámara y tu pantalla están bien alineadas.</>
                ) : (
                  /* Antes decía "tu cámara está a la izquierda" justo después de
                     pedirle que mirara la PANTALLA: mezclaba las dos cosas y se
                     leía como un error del sistema. Se nombra lo que se midió —
                     que no están alineadas — sin inferir dónde está cada una. */
                  <>
                    Tu cámara no está alineada con la pantalla que mirás. Ya lo tuvimos en
                    cuenta, pero conviene corregirlo.
                  </>
                )}
              </p>
              {posicion !== 'centrada' && (
                <p className="text-[13px] text-on-surface-variant mt-1">
                  Si podés, centrala y calibrá de nuevo.
                </p>
              )}
            </>
          )}

          {estado === 'pendiente' && (
            <p className="text-[13px] text-on-surface-variant mt-1">
              Medimos cómo mirás la pantalla para no confundir que estés leyendo con una
              distracción. Ponete como vas a estar durante el examen y tocá «Calibrar ahora».
            </p>
          )}

          {estado === 'sin_camara' && (
            // La cámara es OBLIGATORIA para rendir (el chequeo de requisitos ya
            // no deja pasar sin ella). Decir "podés rendir igual" era falso y lo
            // iba a descubrir recién al no poder empezar.
            <p className="text-[13px] text-on-surface-variant mt-1">
              No pudimos usar la cámara, y sin cámara no se puede rendir. Revisá que le
              hayas dado permiso y que no la esté usando otra aplicación.
            </p>
          )}
        </div>

        {estado === 'midiendo' && (
          <Icon name="progress_activity" className="ae-spin text-[20px] text-primary shrink-0" />
        )}
      </div>

      {/* `scale-x-[-1]` = CONTRA-espejo. Verificado en el navegador: la app no
          aplicaba ningún transform (ni el <video> ni ningún ancestro), así que
          el espejado lo hace la cámara/driver. Esto lo revierte para que el
          alumno vea la imagen REAL y acomodar la cámara no sea adivinanza.
          NO afecta la medición: el gaze se calcula sobre los frames crudos del
          <video> (`createImageBitmap`), que el CSS no toca.
          Tampoco se oculta con `display:none`: un <video> oculto no decodifica
          frames en algunos navegadores y la medición daría siempre null. */}
      <div className="relative w-full max-w-md mx-auto">
        <video
          ref={videoRef}
          muted
          playsInline
          className="w-full aspect-video rounded-xl bg-black object-cover scale-x-[-1]"
        />
        {estado === 'midiendo' && (
          <div className="absolute inset-0 rounded-xl bg-black/45 flex flex-col items-center justify-center gap-1 text-white">
            <span className="text-[44px] font-bold leading-none tabular-nums">{restante}</span>
            <span className="text-[13px]">Mirá la pantalla donde vas a rendir</span>
          </div>
        )}
      </div>

      <div className="flex justify-center">
        <Button
          size="sm"
          icon={estado === 'lista' ? 'refresh' : 'visibility'}
          onClick={() => void calibrar()}
          disabled={estado === 'midiendo'}
        >
          {estado === 'midiendo'
            ? `Calibrando… ${restante}s`
            : estado === 'lista'
              ? 'Calibrar de nuevo'
              : estado === 'sin_camara'
                ? 'Reintentar calibración'
                : 'Calibrar ahora'}
        </Button>
      </div>
    </div>
  );
}

export default CalibracionPaso;
