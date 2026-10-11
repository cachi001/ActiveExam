/**
 * Tarjeta de calibración de mirada. La usa la pantalla `Calibracion`, que es el
 * PASO 3 del ingreso (entre la verificación biométrica y la sala de espera).
 *
 * ## Por qué es un paso y no algo del examen
 *
 * La calibración corría DENTRO de la rendición, con el cronómetro ya andando y
 * un cartel que no decía cómo había salido: le comía tiempo al alumno y era una
 * caja negra. Decisión del dueño (29/8/2026): es un paso propio del wizard, con
 * su resultado a la vista y su botón para repetirla.
 *
 * El baseline queda en `baselineGaze` y el examen lo toma de ahí sin recalibrar.
 *
 * ## Qué hace la calibración
 *
 * Mide hacia dónde mira el alumno cuando mira cada una de las 4 ESQUINAS de la
 * pantalla, en PANTALLA COMPLETA (`CalibracionCuatroPuntos`) — la misma
 * geometría en la que se rinde el examen. De ahí sale el centro (el cero) y el
 * rango real de cada eje, que reemplaza al factor fijo que antes se adivinaba
 * (ver `VERTICAL_TOLERANCE_FACTOR` en `stateTransitionRules.ts`).
 *
 * ## Degradación
 *
 * Si la cámara, el motor de visión o la calibración de 4 puntos fallan, NO
 * bloquea: el examen arranca con el baseline por defecto y su propia
 * calibración de respaldo (un solo punto). Perder la precisión del detector es
 * mucho menos grave que dejar a alguien sin rendir.
 */
import { useCallback, useEffect, useRef, useState, type RefObject } from 'react';

import { Icon, Button } from '../../ui/components';
import { loadRealEngine } from '../../vision/harnessEngineLoader';
import type { VisionEngine } from '../../vision/VisionEngine';
import {
  baselineGazeGuardado,
  guardarBaselineGaze,
  posicionDeLaCamara,
} from '../../proctoring/baselineGaze';
import { CalibracionCuatroPuntos } from '../../proctoring/CalibracionCuatroPuntos';
import type { RangoCalibracion } from '../../proctoring/calibracionRango';

export type EstadoCalibracion = 'pendiente' | 'midiendo' | 'lista' | 'sin_camara' | 'fallida';

interface Props {
  videoRef: RefObject<HTMLVideoElement>;
  estado: EstadoCalibracion;
  onEstado: (e: EstadoCalibracion) => void;
  /** Se llama con el rango completo cada vez que la calibración de 4 puntos
   *  termina con éxito — para poder mandarlo al backend (descriptivo, ver
   *  PATCH /sessions/{id}/calibracion). Opcional: el harness no lo necesita. */
  onRango?: (rango: RangoCalibracion) => void;
}

export function CalibracionPaso({ videoRef, estado, onEstado, onRango }: Props) {
  // De qué lado quedó la cámara, según lo que se acaba de medir.
  const posicion = posicionDeLaCamara(baselineGazeGuardado());
  // La cámara queda PRENDIDA después de medir, para que el alumno se vea y pueda
  // acomodarla antes de recalibrar. Se libera al salir del paso: si siguiera
  // tomada, el `getUserMedia` del examen competiría con este stream.
  const streamRef = useRef<MediaStream | null>(null);
  const [engine, setEngine] = useState<VisionEngine | null>(null);

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
    try {
      await encenderCamara();
      if (!videoRef.current) throw new Error('sin elemento de video');
      const motor = await loadRealEngine();
      setEngine(motor);
      onEstado('midiendo');
    } catch {
      // Sin cámara / sin permiso / motor caído: no bloquea el examen.
      guardarBaselineGaze(null);
      soltarCamara();
      onEstado('sin_camara');
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

  function alCompletarCalibracion(rango: RangoCalibracion | null) {
    setEngine(null);
    if (rango) {
      guardarBaselineGaze(rango.centro, { rangoX: rango.rangoX, rangoY: rango.rangoY });
      onRango?.(rango);
      onEstado('lista');
    } else {
      // No arma un baseline con datos a medias: mejor "sin calibrar" (el examen
      // igual tiene su respaldo) que confiar en un cero mal medido.
      guardarBaselineGaze(null);
      onEstado('fallida');
    }
  }

  return (
    <div className="rounded-2xl border border-outline-variant/50 bg-white p-lg space-y-md text-left">
      <div className="flex items-start gap-sm">
        <div
          className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${
            estado === 'lista'
              ? 'bg-success-container text-success'
              : estado === 'sin_camara' || estado === 'fallida'
                ? 'bg-warning-container text-warning'
                : 'bg-primary-fixed text-primary'
          }`}
        >
          <Icon
            name={
              estado === 'lista'
                ? 'check_circle'
                : estado === 'sin_camara' || estado === 'fallida'
                  ? 'error'
                  : 'visibility'
            }
            className="text-[20px]"
            fill
          />
        </div>
        <div className="min-w-0 flex-1">
          {/* El título de la tarjeta repetía, palabra por palabra, el de la pantalla
              que la contiene. Se muestra el ESTADO, que es lo que cambia y lo que
              el alumno necesita leer. */}
          <p className="text-label-md font-semibold text-on-surface">
            {estado === 'lista'
              ? 'Calibración lista'
              : estado === 'midiendo'
                ? 'Midiendo…'
                : estado === 'sin_camara'
                  ? 'No pudimos usar la cámara'
                  : estado === 'fallida'
                    ? 'No se pudo completar la calibración'
                    : 'Antes de empezar'}
          </p>

          {estado === 'midiendo' && (
            <p className="text-[13px] text-on-surface-variant mt-1">
              Vas a ver 4 puntos marcados, uno por vez. Mirá cada uno hasta que avance solo.
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
              Vas a ver 4 puntos marcados en las esquinas de la pantalla, en pantalla
              completa. Ponete como vas a estar durante el examen y tocá «Calibrar ahora».
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

          {estado === 'fallida' && (
            <p className="text-[13px] text-on-surface-variant mt-1">
              La cámara funciona, pero no llegamos a medir los 4 puntos. Probá de nuevo,
              mirando fijo cada punto marcado hasta que avance solo.
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
          frames en algunos navegadores y la medición daría siempre null. Sigue
          existiendo (y decodificando) aunque la calibración de 4 puntos la
          tape con su overlay de pantalla completa. */}
      <div className="relative w-full max-w-md mx-auto">
        <video
          ref={videoRef}
          muted
          playsInline
          className="w-full aspect-video rounded-xl bg-black object-cover scale-x-[-1]"
        />
      </div>

      <div className="flex justify-center">
        <Button
          size="sm"
          icon={estado === 'lista' ? 'refresh' : 'visibility'}
          onClick={() => {
            // Pantalla completa PRIMERO y SÍNCRONO, en el propio click: pedirla
            // después de un `await` (adentro de `calibrar()`) ya no cuenta como
            // gesto del usuario y el navegador la rechaza (confirmado en
            // Chromium real). `CalibracionCuatroPuntos` solo se encarga de salir.
            void document.documentElement.requestFullscreen?.().catch(() => {});
            void calibrar();
          }}
          disabled={estado === 'midiendo'}
          className="w-full sm:w-auto"
        >
          {estado === 'midiendo'
            ? 'Calibrando…'
            : estado === 'lista'
              ? 'Calibrar de nuevo'
              : estado === 'sin_camara' || estado === 'fallida'
                ? 'Reintentar calibración'
                : 'Calibrar ahora'}
        </Button>
      </div>

      {estado === 'midiendo' && engine && (
        <CalibracionCuatroPuntos
          videoRef={videoRef}
          engine={engine}
          onCompleto={alCompletarCalibracion}
        />
      )}
    </div>
  );
}

export default CalibracionPaso;
