// Navegación unificada de staff (admin / proctor / revisor). Una sola fuente
// para que la sidebar sea consistente en todas las pantallas de staff.
//
// `group` separa las secciones de la sidebar:
//   - 'main'    → operación diaria (dashboard, supervisión, cola, reportes…)
//   - 'config'  → administración del sistema (usuarios, test, configuración…)
// StaffShell renderiza ambos grupos en bloques con un divider intermedio.
export interface StaffNavItem {
  to: string;
  icon: string;
  label: string;
  group: 'main' | 'config';
}

export const STAFF_NAV: StaffNavItem[] = [
  { to: '/admin',                       icon: 'space_dashboard', label: 'Dashboard',               group: 'main' },
  { to: '/admin/examenes',              icon: 'quiz',            label: 'Exámenes',                group: 'main' },
  { to: '/admin/reportes',              icon: 'analytics',       label: 'Reportes y analítica',    group: 'main' },
  { to: '/admin/auditoria',             icon: 'policy',          label: 'Auditoría y privacidad',  group: 'main' },
  // Bloque "proctoring": las 3 vistas de sesiones van juntas y al FINAL del grupo
  // main (justo arriba del divider), en orden de flujo: vivo → cola → grabadas.
  { to: '/proctor',                     icon: 'visibility',      label: 'Supervisión en vivo',     group: 'main' },
  { to: '/revisor',                     icon: 'gavel',           label: 'Cola de revisión',        group: 'main' },
  { to: '/admin/proctoring-sessions',   icon: 'video_library',   label: 'Sesiones grabadas',       group: 'main' },
  // Administración: separadas con divider.
  { to: '/admin/usuarios',              icon: 'manage_accounts', label: 'Usuarios',                group: 'config' },
  { to: '/admin/detection-test',        icon: 'bug_report',      label: 'Test de detección',       group: 'config' },
  { to: '/admin/configuracion',         icon: 'settings',        label: 'Configuración',           group: 'config' },
];
