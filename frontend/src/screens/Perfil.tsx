import { StaffShell } from '../ui/shells';
import { Card, Icon } from '../ui/components';
import { STAFF_NAV } from '../ui/nav';
import { useAuth } from '../lib/authStore';
import MiCuentaCampus, { MiCuentaCampusAyuda } from './configuracion/MiCuentaCampus';
import SeccionSeguridad from './configuracion/SeccionSeguridad';
import type { Rol } from '../lib/types';

const ROL_LABEL: Record<Rol, string> = {
  admin_sistema:   'Admin sistema',
  admin_examenes:  'Admin exámenes',
  tutor:           'Tutor',
  coordinador:     'Coordinador',
  proctor:         'Proctor',
  revisor:         'Revisor',
  auditor:         'Auditor',
  estudiante:      'Estudiante',
};

const ACADEMICO: Rol[] = ['tutor', 'admin_examenes', 'coordinador', 'admin_sistema'];

function formatFecha(iso: string | undefined): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'short' });
}

function InfoField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <p className="text-[12px] font-medium text-on-surface-variant mb-1">{label}</p>
      <div className="text-[14px] text-on-surface">{children}</div>
    </div>
  );
}

export default function Perfil() {
  const principal = useAuth((s) => s.principal);
  const hasRole   = useAuth((s) => s.hasRole);

  const tieneMoodle = hasRole(ACADEMICO);
  const nombre  = principal?.nombre ?? '—';
  const inicial = nombre.charAt(0).toUpperCase();

  return (
    <StaffShell nav={STAFF_NAV} title="Mi perfil" subtitle="Configuración de tu cuenta">
      <div className="max-w-2xl space-y-5 animate-in fade-in duration-500">

        {/* Información Personal */}
        <Card>
          <div className="flex items-center gap-2 mb-5">
            <Icon name="person" className="text-[20px] text-on-surface-variant" />
            <h2 className="text-[15px] font-semibold text-on-surface">Información Personal</h2>
          </div>

          <div className="grid grid-cols-2 gap-x-8 gap-y-5">
            <InfoField label="Nombre completo">
              {[nombre, principal?.apellido].filter(Boolean).join(' ')}
            </InfoField>
            <InfoField label="Legajo / Usuario">
              {principal?.id_institucional ?? '—'}
            </InfoField>

            <InfoField label="Email">
              {principal?.email ?? '—'}
            </InfoField>
            <InfoField label="Estado">
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11.5px] font-medium bg-success-50 text-success-700 border border-success/20">
                Activo
              </span>
            </InfoField>

            <InfoField label="Roles">
              <div className="flex flex-wrap gap-1.5">
                {(principal?.roles ?? []).map((rol) => (
                  <span
                    key={rol}
                    className="inline-flex items-center px-2 py-0.5 rounded-full text-[11.5px] font-medium bg-primary-50 text-primary border border-primary/20"
                  >
                    {ROL_LABEL[rol] ?? rol}
                  </span>
                ))}
              </div>
            </InfoField>
            <InfoField label="Avatar">
              <div className="w-9 h-9 rounded-full bg-primary text-on-primary flex items-center justify-center font-bold text-[15px]">
                {principal?.foto_perfil
                  ? <img src={principal.foto_perfil} alt={nombre} className="w-full h-full rounded-full object-cover" />
                  : inicial}
              </div>
            </InfoField>

            <InfoField label="Fecha de creación">
              {formatFecha(principal?.creado_en)}
            </InfoField>
            <InfoField label="Último acceso">
              {formatFecha(principal?.ultimo_acceso_en)}
            </InfoField>
          </div>
        </Card>

        {/* Cuenta Moodle — solo para roles académicos */}
        {tieneMoodle && (
          <Card>
            <div className="flex items-center gap-2 mb-5">
              <Icon name="sync_alt" className="text-[20px] text-on-surface-variant" />
              <h2 className="text-[15px] font-semibold text-on-surface">Cuenta Moodle</h2>
              {MiCuentaCampusAyuda}
            </div>
            <p className="text-[13px] text-on-surface-variant mb-5">
              Conectá tu cuenta del campus para que las notas de tus comisiones puedan viajar.
            </p>
            <MiCuentaCampus />
          </Card>
        )}

        {/* Seguridad */}
        <Card>
          <div className="flex items-center gap-2 mb-5">
            <Icon name="lock" className="text-[20px] text-on-surface-variant" />
            <h2 className="text-[15px] font-semibold text-on-surface">Seguridad</h2>
          </div>
          <SeccionSeguridad />
        </Card>

      </div>
    </StaffShell>
  );
}
