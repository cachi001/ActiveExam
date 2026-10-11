/**
 * Calibración de mirada en 4 PUNTOS, en PANTALLA COMPLETA.
 *
 * Antes se calibraba mirando un solo punto (el centro), en una ventana normal
 * — pero el examen se rinde en pantalla completa, así que se calibraba en una
 * geometría y se medía en otra. Y "mirá al centro" no marcaba ningún punto: uno
 * miraba su propia cara en el video, otro el texto, otro el botón.
 *
 * Midiendo las 4 ESQUINAS reales de la pantalla se puede calcular el rango de
 * mirada (`calcularRangoCalibracion`) en vez de adivinarlo con un factor fijo
 * (ver `VERTICAL_TOLERANCE_FACTOR` en `stateTransitionRules.ts`).
 *
 * Los puntos van cerca del BORDE de la pantalla, nunca dentro del recuadro de
 * la cámara: adentro calibraría "mirar el recuadro", no la pantalla.
 *
 * Reusa `capturarBaselineGaze` (misma función que el paso previo y el
 * respaldo del examen) — el mismo componente lo usan tanto `CalibracionPaso`
 * (el alumno) como el harness de admin, para que el docente vea EXACTAMENTE
 * lo que vive el alumno, no una aproximación.
 */
import { useEffect, useRef, useState } from 'react';

import { capturarBaselineGaze } from './useExamProctoring';
import { CALIBRACION_DURACION_MS, CALIBRACION_INTERVALO_MS } from './calibracionConstantes';
import {
  ESQUINAS,
  ESQUINA_LABEL,
  calcularRangoCalibracion,
  type Esquina,
  type PuntoGaze,
  type RangoCalibracion,
} from './calibracionRango';
import type { VisionEngine } from '../vision/VisionEngine';

/** Pausa antes de muestrear cada punto nuevo: le da tiempo al ojo de moverse y
 *  asentarse. Sin esto, las primeras muestras capturan el salto (saccade) de
 *  un punto al siguiente, no la mirada fija, y sesgan el promedio. */
const ESPERA_ANTES_DE_MEDIR_MS = 700;

const POSICION: Record<Esquina, string> = {
  arriba_izquierda: 'top-8 left-8 sm:top-12 sm:left-12',
  arriba_derecha: 'top-8 right-8 sm:top-12 sm:right-12',
  abajo_derecha: 'bottom-8 right-8 sm:bottom-12 sm:right-12',
  abajo_izquierda: 'bottom-8 left-8 sm:bottom-12 sm:left-12',
};

const PUNTOS_VACIOS: Record<Esquina, PuntoGaze | null> = {
  arriba_izquierda: null,
  arriba_derecha: null,
  abajo_derecha: null,
  abajo_izquierda: null,
};

interface Props {
  videoRef: React.RefObject<HTMLVideoElement>;
  engine: VisionEngine;
  /** `null` = no se pudo completar (cámara perdida, o se canceló). */
  onCompleto: (resultado: RangoCalibracion | null) => void;
  onCancelar?: () => void;
}

export function CalibracionCuatroPuntos({ videoRef, engine, onCompleto, onCancelar }: Props) {
  const terminadoRef = useRef(false);
  const puntosRef = useRef<Record<Esquina, PuntoGaze | null>>({ ...PUNTOS_VACIOS });
  const [indice, setIndice] = useState(0);
  const [fase, setFase] = useState<'esperando' | 'midiendo'>('esperando');

  const terminar = (resultado: RangoCalibracion | null) => {
    if (terminadoRef.current) return;
    terminadoRef.current = true;
    if (document.fullscreenElement) void document.exitFullscreen().catch(() => {});
    onCompleto(resultado);
  };

  // La pantalla completa la pide el LLAMADOR (el onClick del botón «Calibrar»),
  // no este componente: pedirla acá, en un efecto que corre después de montar,
  // ya no está en la cadena síncrona del click y el navegador la rechaza
  // ("API can only be initiated by a user gesture") — confirmado en Chromium
  // real. Este componente solo se encarga de SALIR al terminar/desmontar.
  useEffect(() => {
    return () => {
      if (document.fullscreenElement) void document.exitFullscreen().catch(() => {});
    };
  }, []);

  // Si la persona sale de pantalla completa a mitad de camino (Escape, alt-tab
  // que la corta), se FUERZA a volver en vez de abortar la calibración — mismo
  // patrón que el lockdown del examen real (`fullscreenLockdown.ts`:
  // "re-intenta requestFullscreen automáticamente"). El pedido ocurre dentro
  // del handler de 'fullscreenchange', que sigue contando como gesto del
  // usuario (la tecla Escape que disparó la salida), a diferencia de pedirlo
  // desde un efecto de montaje sin ningún gesto detrás.
  useEffect(() => {
    function alSalirDeFullscreen() {
      if (!document.fullscreenElement && !terminadoRef.current) {
        void document.documentElement.requestFullscreen?.().catch(() => {});
      }
    }
    document.addEventListener('fullscreenchange', alSalirDeFullscreen);
    return () => document.removeEventListener('fullscreenchange', alSalirDeFullscreen);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let cancelado = false;
    async function medirEsquina() {
      setFase('esperando');
      await new Promise((resolve) => setTimeout(resolve, ESPERA_ANTES_DE_MEDIR_MS));
      if (cancelado || terminadoRef.current) return;
      setFase('midiendo');
      const esquina = ESQUINAS[indice];
      const punto = await capturarBaselineGaze(
        videoRef,
        engine,
        CALIBRACION_DURACION_MS,
        CALIBRACION_INTERVALO_MS,
        () => cancelado || terminadoRef.current,
      );
      if (cancelado || terminadoRef.current) return;
      puntosRef.current = { ...puntosRef.current, [esquina]: punto };
      if (indice + 1 < ESQUINAS.length) {
        setIndice((i) => i + 1);
        return;
      }
      const muestrasPorPunto = Math.max(
        1,
        Math.floor(CALIBRACION_DURACION_MS / CALIBRACION_INTERVALO_MS),
      );
      terminar(calcularRangoCalibracion(puntosRef.current, muestrasPorPunto));
    }
    void medirEsquina();
    return () => {
      cancelado = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [indice]);

  const esquinaActual = ESQUINAS[indice];

  return (
    <div className="fixed inset-0 z-[100] bg-black flex items-center justify-center">
      <div className="text-center text-white space-y-2 max-w-xs px-4">
        <p className="text-[15px] font-semibold">Mirá el punto {ESQUINA_LABEL[esquinaActual]}</p>
        <p className="text-[13px] text-white/70">
          Punto {indice + 1} de {ESQUINAS.length}. Movés los ojos, no la cabeza.
        </p>
        {onCancelar && (
          <button
            type="button"
            onClick={() => {
              terminadoRef.current = true;
              if (document.fullscreenElement) void document.exitFullscreen().catch(() => {});
              onCancelar();
            }}
            className="text-[12px] text-white/50 underline mt-2"
          >
            Cancelar
          </button>
        )}
      </div>
      <div
        className={`absolute ${POSICION[esquinaActual]} w-8 h-8 rounded-full border-4 border-white transition-transform duration-300 ${
          fase === 'midiendo' ? 'bg-primary scale-110' : 'bg-transparent scale-90'
        }`}
      />
    </div>
  );
}

export default CalibracionCuatroPuntos;
