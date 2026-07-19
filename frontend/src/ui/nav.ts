// Navegación unificada de staff (admin / proctor / revisor). Una sola fuente
// para que la sidebar sea consistente en todas las pantallas de staff.
//
// `group` separa las secciones de la sidebar:
//   - 'main'    → operación diaria (dashboard, supervisión, cola, reportes…)
//   - 'config'  → administración del sistema (usuarios, test, configuración…)
// StaffShell renderiza ambos grupos en bloques con un divider intermedio.
//
// `roles` declara qué roles VEN el item. DEBE quedar coherente con los guards de
// rutas de App.tsx (misma política): si un item apunta a una ruta que el rol no
// puede abrir, no se le muestra (si no, clickea y le sale "Sin permisos"). Esta
// lista de roles es la fuente de verdad del filtrado del sidebar; los guards de
// App.tsx son la fuente de verdad del acceso a la ruta. Ambos deben coincidir.
import type { Rol } from '../lib/types';

// Política de roles por área (espeja App.tsx):
//   SUPERVISION = proctor + admin → supervisión en vivo, cola de revisión y
//                 sesiones grabadas (el proctor revisa sesiones de alumnos).
//   ADMIN       = admin_sistema   → dashboard, exámenes, reportes, auditoría,
//                 usuarios, test de detección y configuración.
const SUPERVISION: Rol[] = ['proctor', 'admin_sistema'];
const ADMIN: Rol[] = ['admin_sistema'];

export interface StaffNavItem {
  to: string;
  icon: string;
  label: string;
  group: 'main' | 'config';
  /** Roles que ven este item. Coherente con el guard de la ruta en App.tsx. */
  roles: Rol[];
}

export const STAFF_NAV: StaffNavItem[] = [
  { to: '/admin',                       icon: 'space_dashboard', label: 'Dashboard',               group: 'main',   roles: ADMIN },
  { to: '/admin/examenes',              icon: 'quiz',            label: 'Exámenes',                group: 'main',   roles: ADMIN },
  // Bloque "proctoring": las 3 vistas de sesiones van juntas y al FINAL del grupo
  // main (justo arriba del divider), en orden de flujo: vivo → cola → grabadas.
  // Visibles para proctor + admin (SUPERVISION).
  { to: '/proctor',                     icon: 'visibility',      label: 'Supervisión en vivo',     group: 'main',   roles: SUPERVISION },
  { to: '/revisor',                     icon: 'gavel',           label: 'Cola de revisión',        group: 'main',   roles: SUPERVISION },
  { to: '/admin/proctoring-sessions',   icon: 'history',         label: 'Registro de sesiones',    group: 'main',   roles: SUPERVISION },
  // Administración: separadas con divider. Solo admin.
  { to: '/admin/usuarios',              icon: 'manage_accounts', label: 'Usuarios',                group: 'config', roles: ADMIN },
  { to: '/admin/materias',              icon: 'school',          label: 'Materias y comisiones',   group: 'config', roles: ADMIN },
  { to: '/admin/detection-test',        icon: 'bug_report',      label: 'Test de detección',       group: 'config', roles: ADMIN },
  { to: '/admin/configuracion',         icon: 'settings',        label: 'Configuración',           group: 'config', roles: ADMIN },
];

/** Filtra los items de navegación visibles para un conjunto de roles del usuario. */
export function navItemsParaRoles(roles: readonly Rol[] | undefined): StaffNavItem[] {
  if (!roles || roles.length === 0) return [];
  return STAFF_NAV.filter((item) => item.roles.some((r) => roles.includes(r)));
}
