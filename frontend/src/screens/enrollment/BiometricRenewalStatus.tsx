/**
 * Componente de estado de vigencia de la referencia biométrica (C-22).
 *
 * Muestra: vigente / por vencer / caducada / renovación requerida (por deriva).
 * Permite iniciar la renovación desde el perfil.
 *
 * Spec: biometric-reference-renewal (C-22)
 * - La referencia caducada bloquea rendir hasta renovar.
 * - La renovación anticipada por deriva NO sanciona ni invalida la rendición en curso (L2.5).
 */
import { Icon, Button, Badge } from '../../ui/components';
import { Term } from '../../ui/Term';
import type { ReferenciasBiometrica, VigenciaReferencia } from '../../lib/types';

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

  const formatearFecha = (iso: string) =>
    new Date(iso).toLocaleDateString('es-AR', { day: '2-digit', month: 'long', year: 'numeric' });

  return (
    <div className="space-y-md">
      <div className="flex items-center justify-between gap-md flex-wrap">
        <div className="flex items-center gap-sm">
          <Icon name={config.icon} className={`text-[20px] ${
            config.tone === 'success' ? 'text-success' :
            config.tone === 'warning' ? 'text-warning' :
            config.tone === 'error' ? 'text-error' :
            'text-on-surface-variant'
          }`} fill={config.tone === 'success'} />
          <span className="text-label-md text-on-surface font-semibold">Estado de vigencia</span>
        </div>
        <Badge tone={config.tone} dot>{config.label}</Badge>
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
            referencia actual. La renovación no afecta ni sanciona rendiciones en curso (<Term termKey="l2_5" /> —
            decisión disciplinaria siempre humana).
          </p>
        </div>
      )}

      {config.mostrarBotonRenovar && (
        <Button variant="outline" icon="refresh" onClick={onRenovar} className="w-full sm:w-auto">
          {referencia.vigencia === 'caducada' ? 'Renovar referencia (requerido)' : 'Renovar anticipadamente'}
        </Button>
      )}
    </div>
  );
}
