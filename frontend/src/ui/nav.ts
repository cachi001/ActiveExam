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

// Política de roles por área (espeja App.tsx y CAPABILITY_ROLES del backend).
//
// SUPERVISION incluye a 'revisor' — parece obvio, pero faltaba: la ruta /revisor
// admitía solo proctor+admin, mientras el backend reserva `revisar_sesion`
// (decidir en un solo paso, incluida la anulación) al revisor. Resultado: el
// admin entraba pero recibía 403 al decidir, y el revisor tenía el permiso
// pero no podía entrar. Nadie podía anular por fraude.
//
// ACADEMICO es el área del DOCENTE: exámenes, materias y comisiones — lo suyo.
// Queda deliberadamente FUERA de supervisión, auditoría y configuración: quien
// dicta la materia no supervisa la integridad de su propia rendición ni afloja
// los umbrales con que se la detecta.
const SUPERVISION: Rol[] = ['proctor', 'revisor', 'coordinador', 'admin_sistema'];
const ACADEMICO: Rol[] = ['tutor', 'admin_examenes', 'coordinador', 'admin_sistema'];
const ADMIN: Rol[] = ['admin_sistema'];
const AUDITORIA: Rol[] = ['auditor', 'admin_sistema'];

export interface StaffNavItem {
  to: string;
  icon: string;
  label: string;
  group: 'main' | 'config';
  /** Roles que ven este item. Coherente con el guard de la ruta en App.tsx. */
  roles: Rol[];
}

export const STAFF_NAV: StaffNavItem[] = [
  { to: '/admin',                       icon: 'space_dashboard', label: 'Dashboard',               group: 'main',   roles: [...ACADEMICO, 'proctor', 'revisor', 'auditor'] },
  { to: '/admin/estadisticas',          icon: 'insights',        label: 'Estadísticas',            group: 'main',   roles: ACADEMICO },
  { to: '/admin/examenes',              icon: 'fact_check',      label: 'Exámenes',                group: 'main',   roles: ACADEMICO },
  { to: '/admin/banco-preguntas',       icon: 'library_books',   label: 'Banco de preguntas',       group: 'main',   roles: ACADEMICO },
  // Académico, NO administración del sistema: va en 'main' junto a Exámenes y Banco.
  // Antes estaba en 'config' y para el tutor (cuyo único item de config es este)
  // quedaba un divider separando un item solitario, sin sentido.
  { to: '/admin/materias',              icon: 'school',          label: 'Materias y comisiones',   group: 'main',   roles: ACADEMICO },
  // Bloque "proctoring": las 3 vistas de sesiones van juntas y al FINAL del grupo
  // main (justo arriba del divider), en orden de flujo: vivo → cola → grabadas.
  // Visibles para proctor + admin (SUPERVISION).
  { to: '/proctor',                     icon: 'visibility',      label: 'Supervisión en vivo',     group: 'main',   roles: SUPERVISION },
  { to: '/admin/cola-revision',          icon: 'gavel',           label: 'Cola de revisión',        group: 'main',   roles: SUPERVISION },
  { to: '/admin/proctoring-sessions',   icon: 'history',         label: 'Registro de sesiones',    group: 'main',   roles: SUPERVISION },
  // Administración: separadas con divider. Solo admin.
  { to: '/admin/usuarios',              icon: 'manage_accounts', label: 'Usuarios',                group: 'config', roles: ADMIN },
  { to: '/admin/detection-test',        icon: 'bug_report',      label: 'Test de detección',       group: 'config', roles: ADMIN },
  { to: '/admin/auditoria',             icon: 'verified_user',   label: 'Auditoría',               group: 'config', roles: AUDITORIA },
  { to: '/admin/configuracion',         icon: 'settings',        label: 'Configuración',           group: 'config', roles: ADMIN },
];

/** Filtra los items de navegación visibles para un conjunto de roles del usuario. */
export function navItemsParaRoles(roles: readonly Rol[] | undefined): StaffNavItem[] {
  if (!roles || roles.length === 0) return [];
  return STAFF_NAV.filter((item) => item.roles.some((r) => roles.includes(r)));
}
