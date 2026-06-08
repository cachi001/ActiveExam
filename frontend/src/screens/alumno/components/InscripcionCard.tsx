import { Card, Badge, Button, Icon } from '../../../ui/components';
import type { Inscripcion } from '../../../lib/types';

interface GatePorExamen {
  puede: boolean;
  codigo?: string;
  razon?: string;
}

const ESTADO_CONFIG: Record<Inscripcion['estado'], {
  label: string;
  tone: 'neutral' | 'primary' | 'success' | 'warning' | 'error';
  icon: string;
}> = {
  inscripto: { label: 'Inscripto', tone: 'primary', icon: 'check_circle' },
  pendiente: { label: 'Pendiente', tone: 'warning', icon: 'schedule' },
  habilitado: { label: 'Habilitado para rendir', tone: 'success', icon: 'verified' },
  rendido: { label: 'Rendido', tone: 'neutral', icon: 'assignment_turned_in' },
};

interface InscripcionCardProps {
  inscripcion: Inscripcion;
  gate: GatePorExamen | undefined;
  verificando: boolean;
  onRendir: () => void;
  onCompletarAcuse: () => void;
  onIrAPerfil: () => void;
}

export function InscripcionCard({
  inscripcion,
  gate,
  verificando,
  onRendir,
  onCompletarAcuse,
  onIrAPerfil,
}: InscripcionCardProps) {
  const config = ESTADO_CONFIG[inscripcion.estado];
  const fecha = new Date(inscripcion.fecha);
  const puedeRendirEsteExamen = gate?.puede ?? false;
  const codigoGate = gate?.codigo;

  return (
    <Card className="space-y-md">
      {/* C-58 D6: en mobile el badge baja a su propia línea (flex-col) para que el
          nombre del examen use el ancho completo; en sm+ vuelve a la derecha.
          El flex-1+min-w-0 del título comprimía el texto a "Exa..." cuando el badge
          competía por la misma fila — separarlos por breakpoint lo resuelve. */}
      <div className="flex flex-col sm:flex-row sm:items-start gap-md">
        <div className="flex items-start gap-md min-w-0 flex-1">
          <div className="w-11 h-11 rounded-xl bg-primary-fixed text-primary flex items-center justify-center shrink-0">
            <Icon name={config.icon} />
          </div>
          <div className="min-w-0 flex-1">
            {/* line-clamp-2 en mobile (2 líneas legibles), truncate a 1 línea en sm+ */}
            <p className="text-label-md font-semibold text-on-surface line-clamp-2 sm:truncate">{inscripcion.nombre_examen}</p>
            <p className="text-label-sm text-on-surface-variant line-clamp-2">
              {inscripcion.nombre_materia} · {fecha.toLocaleDateString('es-AR', { day: '2-digit', month: 'short', year: 'numeric' })}
            </p>
          </div>
        </div>
        <Badge tone={config.tone} dot>{config.label}</Badge>
      </div>

      {inscripcion.estado === 'habilitado' && (
        // C-58 D6: flex-col en mobile, flex-row en sm+ para que el <p> y el Button no compriman
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-sm pt-sm border-t border-outline-variant/40">
          {/* C-63: badge de verificación alternativa pendiente */}
          {codigoGate === 'via_alternativa_pendiente' && (
            <div className="flex items-center gap-sm bg-secondary-container rounded-lg px-sm py-xs w-full">
              <Icon name="support_agent" className="text-[18px] text-secondary shrink-0" />
              <span className="text-label-sm text-on-surface">
                Verificación alternativa pendiente — Pendiente de habilitación por proctor
              </span>
            </div>
          )}

          {puedeRendirEsteExamen ? (
            <Button
              onClick={onRendir}
              disabled={verificando}
              icon={verificando ? undefined : 'play_arrow'}
              className="h-10"
            >
              {verificando ? (
                <span className="inline-flex items-center gap-xs">
                  <Icon name="progress_activity" className="ae-spin text-[16px]" />
                  Verificando…
                </span>
              ) : 'Rendir'}
            </Button>
          ) : codigoGate === 'via_alternativa_pendiente' ? (
            // C-63: botón Rendir deshabilitado con el motivo
            <Button
              onClick={onRendir}
              disabled
              icon="play_arrow"
              className="h-10 opacity-50 cursor-not-allowed"
            >
              Pendiente de habilitación por proctor
            </Button>
          ) : codigoGate === 'acuse_examen_faltante' ? (
            <>
              <p className="text-label-sm text-on-surface-variant flex-1 min-w-0">
                Falta el acuse de consentimiento para este examen.
              </p>
              <Button
                variant="secondary"
                onClick={onCompletarAcuse}
                icon="assignment_turned_in"
                className="h-10 shrink-0"
              >
                Completar acuse del examen
              </Button>
            </>
          ) : (
            <>
              <p className="text-label-sm text-on-surface-variant flex-1 min-w-0">
                {codigoGate === 'biometria_caducada'
                  ? 'Tu referencia biométrica caducó. Renovála para poder rendir.'
                  : codigoGate === 'biometria_renovacion_requerida'
                    ? 'Se requiere renovación de biometría. Actualizá tu perfil.'
                    : codigoGate === 'consentimiento_version_desactualizada'
                      ? 'Hay una nueva versión del consentimiento. Actualizá tu perfil.'
                      : 'Completá tu perfil para poder rendir.'}
              </p>
              <Button
                variant={codigoGate === 'biometria_caducada' ? 'danger' : 'outline'}
                onClick={onIrAPerfil}
                icon="manage_accounts"
                className="h-10 shrink-0"
              >
                {codigoGate === 'biometria_caducada' ? 'Renovar biometría' : 'Completar perfil'}
              </Button>
            </>
          )}
        </div>
      )}

      {inscripcion.estado === 'rendido' && (
        <div className="pt-sm border-t border-outline-variant/40">
          <span className="text-label-sm text-on-surface-variant">
            Examen completado. El resultado está sujeto a revisión académica.
          </span>
        </div>
      )}
    </Card>
  );
}
