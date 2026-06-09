// Navegación unificada de staff (admin / proctor / revisor). Una sola fuente
// para que la sidebar sea consistente en todas las pantallas de staff.
export const STAFF_NAV = [
  { to: '/admin', icon: 'space_dashboard', label: 'Dashboard' },
  { to: '/admin/examenes', icon: 'quiz', label: 'Exámenes' },
  { to: '/proctor', icon: 'visibility', label: 'Supervisión en vivo' },
  { to: '/revisor', icon: 'gavel', label: 'Cola de revisión' },
  { to: '/admin/reportes', icon: 'analytics', label: 'Reportes y analítica' },
  { to: '/admin/auditoria', icon: 'policy', label: 'Auditoría y privacidad' },
  { to: '/admin/detection-test', icon: 'bug_report', label: 'Test de detección' },
  // C-46: Sesiones grabadas del backend slim de proctoring
  { to: '/admin/proctoring-sessions', icon: 'video_library', label: 'Sesiones grabadas' },
  // C-61: Gestión de usuarios
  { to: '/admin/usuarios', icon: 'manage_accounts', label: 'Usuarios' },
  // #10: Configuración del sistema (scoring por tipo de evento + ajustes globales futuros)
  { to: '/admin/configuracion', icon: 'settings', label: 'Configuración' },
];
