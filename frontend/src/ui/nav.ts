// Navegación unificada de staff (admin / coordinador / tutor). Una sola fuente
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
// c-76: los roles 'proctor' y 'revisor' fueron ELIMINADOS del dominio.
//
// SUPERVISION_VIVO = capacidad `supervisar_vivo` ({TUTOR, COORDINADOR,
// ADMIN_SISTEMA} en el backend, D2): el tutor supervisa en vivo y ve el
// registro histórico, ACOTADO a su comisión (el scoping por comisión lo
// aplica el backend — acá solo se decide si el item se muestra).
//
// COLA_REVISION = capacidad `revisar_sesion` ({COORDINADOR, ADMIN_SISTEMA}):
// el veredicto (aprobar/anular) — el TUTOR NUNCA lo emite (D3, regla dura #5).
// Antes ambas áreas compartían el mismo array `SUPERVISION`, lo que hubiera
// exigido elegir entre bloquear al tutor de supervisión en vivo o dejarlo
// entrar a la cola de decisión — son capacidades distintas, así que se separan.
const SUPERVISION_VIVO: Rol[] = ['tutor', 'profesor', 'coordinador', 'admin_sistema'];
const COLA_REVISION: Rol[] = ['coordinador', 'admin_sistema'];
//
// ACADEMICO es el área del DOCENTE: exámenes, materias y comisiones — lo suyo.
// Queda deliberadamente FUERA de supervisión, auditoría y configuración: quien
// dicta la materia no supervisa la integridad de su propia rendición ni afloja
// los umbrales con que se la detecta.
// c-76-2: 'admin_examenes' fue ELIMINADO del dominio (solo existe un rol "Admin").
const ACADEMICO: Rol[] = ['tutor', 'profesor', 'coordinador', 'admin_sistema'];
// c-78 (E-03/E-04): CREAR exámenes y el BANCO de preguntas salen del área del
// TUTOR. No es solo ocultar el ítem: los endpoints tienen su propia capacidad
// (`crear_examenes` / `gestionar_banco`) y responden 403 aunque se escriba la
// URL a mano. El tutor conserva Notas, Materias y Supervisión de lo suyo.
const CREAR_EXAMENES: Rol[] = ['profesor', 'coordinador', 'admin_sistema'];
const ADMIN: Rol[] = ['admin_sistema'];
// c-79: capacidad `ver_estadisticas` del backend — deliberadamente SIN tutor.
// Los filtros de /stats son query params libres sin scoping por comisión; el
// tutor ve SU rendimiento vía las pantallas de ACADEMICO (Notas, Exámenes),
// no el agregado institucional de comisiones ajenas.
const VER_ESTADISTICAS: Rol[] = ['profesor', 'coordinador', 'admin_sistema'];

export interface StaffNavItem {
  to: string;
  icon: string;
  label: string;
  group: 'main' | 'config';
  /** Roles que ven este item. Coherente con el guard de la ruta en App.tsx. */
  roles: Rol[];
}

export const STAFF_NAV: StaffNavItem[] = [
  { to: '/admin',                       icon: 'space_dashboard', label: 'Dashboard',               group: 'main',   roles: ACADEMICO },
  { to: '/admin/estadisticas',          icon: 'insights',        label: 'Estadísticas',            group: 'main',   roles: VER_ESTADISTICAS },
  { to: '/admin/examenes',              icon: 'fact_check',      label: 'Exámenes',                group: 'main',   roles: CREAR_EXAMENES },
  // Alumnos que rindieron + sync a Moodle, sin pasar por el detalle de cada
  // examen (antes: Exámenes → click en la fila → scroll → "Ver alumnos que
  // rindieron"). Reusa la misma pantalla de resultados, solo cambia la entrada.
  { to: '/admin/notas',                 icon: 'grading',         label: 'Notas',                   group: 'main',   roles: ACADEMICO },
  { to: '/admin/banco-preguntas',       icon: 'library_books',   label: 'Banco de preguntas',       group: 'main',   roles: CREAR_EXAMENES },
  // Académico, NO administración del sistema: va en 'main' junto a Exámenes y Banco.
  // Antes estaba en 'config' y para el tutor (cuyo único item de config es este)
  // quedaba un divider separando un item solitario, sin sentido.
  { to: '/admin/materias',              icon: 'school',          label: 'Materias y comisiones',   group: 'main',   roles: ACADEMICO },
  // Bloque "proctoring": las 3 vistas de sesiones van juntas y al FINAL del grupo
  // main (justo arriba del divider), en orden de flujo: vivo → cola → grabadas.
  // Supervisión en vivo + registro: tutor (acotado a su comisión) + coordinador + admin.
  { to: '/proctor',                     icon: 'visibility',      label: 'Supervisión en vivo',     group: 'main',   roles: SUPERVISION_VIVO },
  { to: '/admin/proctoring-sessions',   icon: 'history',         label: 'Registro de sesiones',    group: 'main',   roles: SUPERVISION_VIVO },
  // Cola de revisión (veredicto): SOLO coordinador + admin — el tutor NUNCA decide (D3).
  { to: '/admin/cola-revision',          icon: 'gavel',           label: 'Cola de revisión',        group: 'main',   roles: COLA_REVISION },
  // Administración: separadas con divider. Solo admin.
  { to: '/admin/usuarios',              icon: 'manage_accounts', label: 'Usuarios',                group: 'config', roles: ADMIN },
  { to: '/admin/detection-test',        icon: 'bug_report',      label: 'Test de detección',       group: 'config', roles: ADMIN },
  { to: '/admin/auditoria',             icon: 'verified_user',   label: 'Auditoría',               group: 'config', roles: ADMIN },
  { to: '/admin/lti',                   icon: 'lan',             label: 'Integración LTI',         group: 'config', roles: ADMIN },
  { to: '/admin/configuracion',         icon: 'settings',        label: 'Configuración',           group: 'config', roles: ADMIN },
];

/** Filtra los items de navegación visibles para un conjunto de roles del usuario. */
export function navItemsParaRoles(roles: readonly Rol[] | undefined): StaffNavItem[] {
  if (!roles || roles.length === 0) return [];
  return STAFF_NAV.filter((item) => item.roles.some((r) => roles.includes(r)));
}
