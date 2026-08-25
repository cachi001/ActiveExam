import { StaffShell } from '../ui/shells';
import { Card, Icon } from '../ui/components';
import { STAFF_NAV } from '../ui/nav';
import { useAuth } from '../lib/authStore';
import { usernameVisible } from '../lib/identidadVisible';
import MiCuentaCampus, { MiCuentaCampusAyuda } from './configuracion/MiCuentaCampus';
import SeccionSeguridad from './configuracion/SeccionSeguridad';
import type { Rol } from '../lib/types';

// c-76: 'proctor' y 'revisor' eliminados del enum Rol — el coordinador absorbe
// la supervisión global en vivo y el veredicto.
// c-76-2: 'admin_examenes' y 'auditor' eliminados del enum Rol — solo existe
// un rol "Admin" (admin_sistema).
// c-78: 'profesor' agregado — arma exámenes y banco, sin veredicto.
const ROL_LABEL: Record<Rol, string> = {
  admin_sistema:   'Admin',
  tutor:           'Tutor',
  profesor:        'Profesor',
  coordinador:     'Coordinador',
  estudiante:      'Estudiante',
};

const ACADEMICO: Rol[] = ['tutor', 'profesor', 'coordinador', 'admin_sistema'];

function formatFecha(iso: string | undefined): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'short' });
}

function InfoField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <p className="text-label-sm text-on-surface-variant mb-1">{label}</p>
      <div className="text-body-md text-on-surface">{children}</div>
    </div>
  );
}

function SectionTitle({ icon, children, extra }: { icon: string; children: React.ReactNode; extra?: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2.5 mb-6">
      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary-50 text-primary">
        <Icon name={icon} className="text-[22px]" />
      </span>
      <h2 className="text-title-lg text-on-surface">{children}</h2>
      {extra}
    </div>
  );
}

export default function Perfil() {
  const principal = useAuth((s) => s.principal);
  const hasRole   = useAuth((s) => s.hasRole);

  const tieneMoodle = hasRole(ACADEMICO);
  const nombre  = principal?.nombre ?? '—';
  const nombreCompleto = [nombre, principal?.apellido].filter(Boolean).join(' ') || '—';
  const inicial = nombre.charAt(0).toUpperCase();

  return (
    <StaffShell nav={STAFF_NAV} title="Mi perfil" subtitle="Configuración de tu cuenta">
      <div className="max-w-4xl mx-auto space-y-6 animate-in fade-in duration-500">

        {/* Encabezado: avatar al lado del nombre + roles (no como un campo más) */}
        <Card>
          <div className="flex items-center gap-5">
            <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-full bg-primary text-on-primary text-headline-lg font-bold">
              {principal?.foto_perfil
                ? <img src={principal.foto_perfil} alt={nombre} className="h-full w-full rounded-full object-cover" />
                : inicial}
            </div>
            <div className="min-w-0">
              <h2 className="text-headline-md text-on-surface truncate">{nombreCompleto}</h2>
              <p className="text-body-md text-on-surface-variant truncate">{principal?.email ?? '—'}</p>
              <div className="mt-2.5 flex flex-wrap gap-1.5">
                {(principal?.roles ?? []).map((rol) => (
                  <span
                    key={rol}
                    className="inline-flex items-center rounded-full border border-primary/20 bg-primary-50 px-2.5 py-0.5 text-label-sm font-medium text-primary"
                  >
                    {ROL_LABEL[rol] ?? rol}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </Card>

        {/* Información Personal */}
        <Card>
          <SectionTitle icon="person">Información Personal</SectionTitle>

          <div className="grid grid-cols-1 gap-x-10 gap-y-6 sm:grid-cols-2">
            <InfoField label="Nombre completo">{nombreCompleto}</InfoField>
            <InfoField label="Usuario">
              {/* c-78: nunca el sintetico `lti:1:7`. Ver lib/identidadVisible.ts. */}
              <span className="font-mono">
                {usernameVisible(principal?.username, principal?.email)}
              </span>
            </InfoField>

            <InfoField label="Email">
              {principal?.email ?? '—'}
            </InfoField>
            <InfoField label="Estado">
              <span className="inline-flex items-center rounded-full border border-success/20 bg-success-50 px-2 py-0.5 text-label-sm font-medium text-success-700">
                Activo
              </span>
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
            <SectionTitle icon="sync_alt" extra={MiCuentaCampusAyuda}>Cuenta Moodle</SectionTitle>
            <p className="text-body-md text-on-surface-variant mb-5">
              Conectá tu cuenta del campus para que las notas de tus comisiones puedan viajar.
            </p>
            <MiCuentaCampus />
          </Card>
        )}

        {/* Seguridad */}
        <Card>
          <SectionTitle icon="lock">Seguridad</SectionTitle>
          <SeccionSeguridad />
        </Card>

      </div>
    </StaffShell>
  );
}
