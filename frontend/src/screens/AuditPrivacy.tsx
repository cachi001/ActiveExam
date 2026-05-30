import { StaffShell } from '../ui/shells';
import { Icon, Card, Badge, SectionTitle, Button, Stat } from '../ui/components';
import { ADMIN_NAV } from './AdminDashboard';

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
      <div className="space-y-lg">
        <div className="grid sm:grid-cols-3 gap-lg">
          <Stat icon="schedule" label="Retención" value="30 días" sub="luego eliminación automática" />
          <Stat icon="enhanced_encryption" label="Cifrado" value="At-rest + WORM" sub="MinIO Object Lock" />
          <Stat icon="fingerprint" label="Embedding" value="Dato sensible" sub="responsabilidad reforzada" />
        </div>

        <div className="grid lg:grid-cols-3 gap-lg">
          <div className="lg:col-span-2">
            <Card>
              <SectionTitle sub="Registro inmutable de acciones (audit log)">Auditoría</SectionTitle>
              <div className="space-y-base">
                {AUDITORIA.map((a, i) => (
                  <div key={i} className="flex items-start gap-sm p-sm rounded-xl bg-surface-container-low border border-outline-variant/30">
                    <div className="w-9 h-9 rounded-full bg-surface-container flex items-center justify-center text-on-surface-variant shrink-0">
                      <Icon name="history" className="text-[18px]" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-base">
                        <span className="text-label-md font-semibold text-on-surface">{a.accion}</span>
                        <Badge tone={a.tono}>{a.actor}</Badge>
                      </div>
                      <p className="text-label-sm text-on-surface-variant mt-base">{a.detalle}</p>
                      <p className="text-label-sm text-on-surface-variant font-mono mt-base">{a.ts}</p>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </div>

          <div className="space-y-lg">
            <Card className="space-y-sm">
              <h3 className="font-headline text-title-lg text-on-surface">Derechos del titular</h3>
              <p className="text-label-sm text-on-surface-variant">Ley 25.326 · AAIP</p>
              {DSR.map((d) => (
                <div key={d.titulo} className="flex items-start gap-sm p-base rounded-xl bg-surface-container-low border border-outline-variant/30">
                  <Icon name={d.icon} className="text-primary text-[20px]" />
                  <div>
                    <p className="text-label-md font-semibold text-on-surface">{d.titulo}</p>
                    <p className="text-label-sm text-on-surface-variant">{d.desc}</p>
                  </div>
                </div>
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
