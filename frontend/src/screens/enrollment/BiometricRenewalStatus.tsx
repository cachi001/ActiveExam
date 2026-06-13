/**
 * Componente de estado de vigencia de la referencia biométrica (C-22).
 *
 * Muestra: vigente / por vencer / caducada / renovación requerida (por deriva).
 * Permite iniciar la renovación desde el perfil.
 *
 * Spec: biometric-reference-renewal (C-22)
 * - La referencia caducada bloquea rendir hasta renovar.
 * - La renovación anticipada por deriva NO sanciona ni invalida la rendición en curso (L2.5).
 *
 * C-65 Task 7.2: límite suave de re-captura.
 * - MAX_RECAPTURAS_VENTANA: máximo de re-capturas permitidas en la ventana.
 * - VENTANA_MS: duración de la ventana en ms (30 min).
 * - Al alcanzar el límite, el botón se deshabilita con copy explicativo. Sin sanción.
 */
import { useState, useCallback } from 'react';
import { Icon, Button } from '../../ui/components';
import { Term } from '../../ui/Term';
import type { ReferenciasBiometrica, VigenciaReferencia } from '../../lib/types';

// C-65: Límite suave de re-captura (anti fishing de liveness).
const MAX_RECAPTURAS_VENTANA = 3;
const VENTANA_MS = 30 * 60 * 1000; // 30 minutos

interface Props {
  referencia: ReferenciasBiometrica;
  onRenovar: () => void;
}

const VIGENCIA_CONFIG: Record<VigenciaReferencia, {
  tone: 'success' | 'warning' | 'error' | 'neutral';
  label: string;
  icon: string;
  descripcion: string;
  mostrarBotonRenovar: boolean;
}> = {
  vigente: {
    tone: 'success',
    label: 'Vigente',
    icon: 'verified_user',
    descripcion: 'Tu referencia biométrica está activa y en buen estado.',
    mostrarBotonRenovar: false,
  },
  por_vencer: {
    tone: 'warning',
    label: 'Por vencer',
    icon: 'schedule',
    descripcion: 'Tu referencia vence pronto. Podés renovarla anticipadamente.',
    mostrarBotonRenovar: true,
  },
  caducada: {
    tone: 'error',
    label: 'Caducada',
    icon: 'cancel',
    descripcion: 'Tu referencia venció. Necesitás renovarla para poder rendir.',
    mostrarBotonRenovar: true,
  },
  renovacion_requerida: {
    tone: 'warning',
    label: 'Renovación requerida',
    icon: 'refresh',
    descripcion: 'Se detectó deriva del embedding durante las verificaciones. Se recomienda renovar la referencia.',
    mostrarBotonRenovar: true,
  },
};

export function BiometricRenewalStatus({ referencia, onRenovar }: Props) {
  const config = VIGENCIA_CONFIG[referencia.vigencia];

  // C-65 Task 7.2: Límite suave de re-captura — estado local de la ventana.
  // timestamps[] almacena los epoch ms de cada re-captura en la ventana actual.
  const [timestamps, setTimestamps] = useState<number[]>([]);

  const handleRenovar = useCallback(() => {
    const ahora = Date.now();
    // Filtrar re-capturas fuera de la ventana actual
    const enVentana = timestamps.filter((t) => ahora - t < VENTANA_MS);
    if (enVentana.length >= MAX_RECAPTURAS_VENTANA) {
      // Límite alcanzado — no llama a onRenovar, no sanciona.
      return;
    }
    setTimestamps([...enVentana, ahora]);
    onRenovar();
  }, [timestamps, onRenovar]);

  // Calcular estado del límite para el botón
  const ahora = Date.now();
  const enVentanaActual = timestamps.filter((t) => ahora - t < VENTANA_MS);
  const limiteAlcanzado = enVentanaActual.length >= MAX_RECAPTURAS_VENTANA;

  const formatearFecha = (iso: string) =>
    new Date(iso).toLocaleDateString('es-AR', { day: '2-digit', month: 'long', year: 'numeric' });

  return (
    <div className="space-y-md">
      {/* El badge de estado (Vigente / Caducada / …) lo muestra el RequisitoCard
          contenedor; aquí NO se repite para no duplicarlo en pantalla. */}
      <div className="flex items-center gap-sm">
        <Icon name={config.icon} className={`text-[20px] ${
          config.tone === 'success' ? 'text-success' :
          config.tone === 'warning' ? 'text-warning' :
          config.tone === 'error' ? 'text-error' :
          'text-on-surface-variant'
        }`} fill={config.tone === 'success'} />
        <span className="text-label-md text-on-surface font-semibold">Estado de vigencia</span>
      </div>

      <p className="text-label-sm text-on-surface-variant">{config.descripcion}</p>

      <div className="grid grid-cols-2 gap-sm text-label-sm">
        <div>
          <p className="text-on-surface-variant uppercase tracking-wide text-[10px] font-semibold mb-base">Capturada</p>
          <p className="text-on-surface font-semibold">{formatearFecha(referencia.fecha_captura)}</p>
        </div>
        <div>
          <p className="text-on-surface-variant uppercase tracking-wide text-[10px] font-semibold mb-base">Vence</p>
          <p className={`font-semibold ${
            referencia.vigencia === 'caducada' ? 'text-error' :
            referencia.vigencia === 'por_vencer' ? 'text-warning' :
            'text-on-surface'
          }`}>{formatearFecha(referencia.fecha_expiracion)}</p>
        </div>
      </div>

      {/* Nota sobre renovación anticipada por deriva */}
      {referencia.renovacion_anticipada_requerida && (
        <div className="flex items-start gap-sm bg-warning-container/60 rounded-xl p-sm border border-warning/20">
          <Icon name="info" className="text-warning text-[16px] shrink-0 mt-px" />
          <p className="text-label-sm text-on-surface">
            La verificación silenciosa detectó <strong>deriva del <Term termKey="embedding">embedding</Term></strong> respecto de la
            referencia actual. La renovación no afecta ni sanciona rendiciones en curso (la decisión es siempre humana).
          </p>
        </div>
      )}

      {/* C-65 Task 7.2: copy explicativo cuando el límite suave está alcanzado */}
      {limiteAlcanzado && (
        <div className="flex items-start gap-sm bg-surface-variant/60 rounded-xl p-sm border border-outline-variant/20">
          <Icon name="info" className="text-on-surface-variant text-[16px] shrink-0 mt-px" />
          <p className="text-label-sm text-on-surface-variant">
            Alcanzaste el límite de re-capturas por ahora. Podés volver a intentarlo en 30 minutos.
            Esto no afecta tu rendición ni genera ninguna sanción.
          </p>
        </div>
      )}

      {config.mostrarBotonRenovar ? (
        <Button
          variant="outline"
          icon="refresh"
          onClick={handleRenovar}
          disabled={limiteAlcanzado}
          className="w-full sm:w-auto"
        >
          {referencia.vigencia === 'caducada' ? 'Renovar referencia (requerido)' : 'Renovar anticipadamente'}
        </Button>
      ) : (
        // Vigente: igual ofrecemos un "Rehacer" suave por si la captura quedó mal
        // (rostro mal encuadrado, luz pobre, falla de red al guardar, etc.).
        // Usa el mismo flujo de renovación (reemplaza la referencia vigente).
        <Button
          variant="outline"
          size="sm"
          icon="refresh"
          onClick={handleRenovar}
          disabled={limiteAlcanzado}
          className="w-full sm:w-auto"
        >
          {limiteAlcanzado ? 'Límite de re-capturas alcanzado' : 'Rehacer captura'}
        </Button>
      )}
    </div>
  );
}
