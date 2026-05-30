// Navegación unificada de staff (admin / proctor / revisor). Una sola fuente
// para que la sidebar sea consistente en todas las pantallas de staff.
export const STAFF_NAV = [
  { to: '/admin', icon: 'space_dashboard', label: 'Dashboard' },
  { to: '/admin/examenes', icon: 'quiz', label: 'Exámenes' },
  { to: '/admin/configurar', icon: 'tune', label: 'Configurar examen' },
  { to: '/proctor', icon: 'visibility', label: 'Supervisión en vivo' },
  { to: '/revisor', icon: 'gavel', label: 'Cola de revisión' },
  { to: '/revisor/detalle', icon: 'description', label: 'Detalle de sesión' },
  { to: '/admin/reportes', icon: 'analytics', label: 'Reportes y analítica' },
  { to: '/admin/auditoria', icon: 'policy', label: 'Auditoría y privacidad' },
];
