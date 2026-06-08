import { StaffShell } from '../ui/shells';
import { Icon, Card, SectionTitle, Button } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { StatCard } from './proctoring/StatCard';
import { ADMIN_NAV } from './AdminDashboard';
import { AuditLogItem } from './admin/components/AuditLogItem';
import { DsrCard } from './admin/components/DsrCard';

const AUDITORIA = [
  { ts: '2026-05-30 16:42:10', actor: 'Prof. Martín Acuña', accion: 'Resolución de revisión', detalle: 'Sesión S-93041 derivada a disciplina', tono: 'error' as const },
  { ts: '2026-05-30 16:21:55', actor: 'Sistema', accion: 'Re-inferencia server-side', detalle: 'Evidencia clip_tomas_01 re-hasheada y firmada (Ed25519)', tono: 'neutral' as const },
  { ts: '2026-05-30 15:58:31', actor: 'Sistema', accion: 'Captura de evidencia', detalle: 'Evento alta: múltiples rostros (SESS-00394)', tono: 'warning' as const },
  { ts: '2026-05-30 14:02:00', actor: 'Emiliano Cáceres', accion: 'Consentimiento registrado', detalle: 'Versión 2026.1 · acción afirmativa', tono: 'success' as const },
  { ts: '2026-05-30 13:55:12', actor: 'Lucía Mendoza', accion: 'Examen publicado', detalle: 'Anatomía I (Cátedra B) programado', tono: 'primary' as const },
];

const DSR = [
  { icon: 'visibility', titulo: 'Acceso', desc: 'El estudiante puede solicitar copia de sus datos tratados.' },
  { icon: 'edit', titulo: 'Rectificación', desc: 'Corrección de datos personales inexactos.' },
  { icon: 'delete', titulo: 'Supresión', desc: 'Eliminación del embedding al egreso (salvo hold).' },
  { icon: 'gavel', titulo: 'Reclamo AAIP', desc: 'Derecho a reclamar ante la autoridad de aplicación.' },
];

export default function AuditPrivacy() {
  return (
    <StaffShell nav={ADMIN_NAV} title="Auditoría y privacidad">
      <div className="space-y-lg animate-in fade-in duration-500">
        {/* Header */}
        <div className="flex items-start justify-between gap-md flex-wrap">
          <div className="flex items-start gap-2 min-w-0">
            <p className="text-[13px] text-on-surface-variant">
              Registro inmutable de acciones y cadena de custodia. Derechos del titular disponibles abajo.
            </p>
            <HelpButton title="Auditoría y privacidad">
              <p>
                Registro <strong>inmutable</strong> de todas las acciones relevantes del sistema y
                cadena de custodia de la evidencia (hash + firma server-side).
              </p>
              <p>
                Abajo encontrás los <em>derechos del titular</em> que exige la Ley 25.326
                argentina: acceso, rectificación, supresión y reclamo ante la AAIP.
              </p>
              <p>
                La evidencia que se elimina por DSR queda en hold si hay un procedimiento
                disciplinario activo (regla #7 del proyecto).
              </p>
            </HelpButton>
          </div>
          <div className="flex items-center gap-base px-sm py-base rounded-lg bg-primary-fixed/50
            border border-primary/20 text-label-sm text-on-primary-fixed-variant">
            <Icon name="lock" className="text-[16px] shrink-0" fill />
            <span>Soberanía de datos</span>
          </div>
        </div>

        <div className="grid sm:grid-cols-3 gap-md">
          <StatCard icon="schedule" label="Retención" value="30 días" sub="luego eliminación automática" tono="primary" />
          <StatCard icon="enhanced_encryption" label="Evidencia" value="Protegida" sub="cifrada e inalterable" tono="success" />
          <StatCard icon="fingerprint" label="Embedding" value="Dato sensible" sub="responsabilidad reforzada" tono="warning" />
        </div>

        <div className="grid lg:grid-cols-3 gap-lg">
          <div className="lg:col-span-2">
            <Card>
              <SectionTitle sub="Registro inmutable de acciones (audit log)">Auditoría</SectionTitle>
              <div className="space-y-base">
                {AUDITORIA.map((a, i) => (
                  <AuditLogItem key={i} entrada={a} />
                ))}
              </div>
            </Card>
          </div>

          <div className="space-y-lg">
            <Card className="space-y-sm">
              <SectionTitle sub="AAIP">Derechos del titular</SectionTitle>
              {DSR.map((d) => (
                <DsrCard key={d.titulo} derecho={d} />
              ))}
              <Button variant="outline" icon="download" className="w-full">Exportar registro de tratamiento</Button>
            </Card>

            <Card className="bg-primary-fixed/40 border-primary-fixed-dim/50">
              <div className="flex items-start gap-sm">
                <Icon name="shield_lock" className="text-primary" fill />
                <p className="text-label-md text-on-primary-fixed-variant">
                  Soberanía de datos completa: toda la evidencia vive en infraestructura self-hosted de la universidad. Sin terceros.
                </p>
              </div>
            </Card>
          </div>
        </div>
      </div>
    </StaffShell>
  );
}
