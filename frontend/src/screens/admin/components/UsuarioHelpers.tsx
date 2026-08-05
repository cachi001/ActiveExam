import { Badge } from '../../../ui/components';
import {
  getRolLabel,
  ROL_DESCRIPCIONES,
  ROL_LABELS,
  ROLES_VALIDOS,
  ROLES_FORMULARIO,
} from '../../../lib/constants/roles';
import type { UsuarioAdmin } from '../../../lib/types';

export { ROL_DESCRIPCIONES, ROL_LABELS, ROLES_VALIDOS, ROLES_FORMULARIO };

export type ModoFormulario = 'crear' | 'editar';

export interface FormState {
  id_institucional: string;
  email: string;
  nombre: string;
  apellido: string;
  password: string;
  roles: string[];
}

export const FORM_VACIO: FormState = {
  id_institucional: '',
  email: '',
  nombre: '',
  apellido: '',
  password: '',
  roles: [],
};

export const OPCIONES_ROL = [
  { value: '', label: 'Todos los roles' },
  { value: 'admin_sistema', label: 'Administrador' },
  { value: 'proctor', label: 'Proctor' },
  { value: 'estudiante', label: 'Estudiante' },
];

export const OPCIONES_ESTADO = [
  { value: 'activo', label: 'Activos' },
  { value: 'inactivo', label: 'Inactivos' },
  { value: 'todos', label: 'Todos' },
];

export function RolBadge({ rol }: { rol: string }) {
  return <Badge tone="primary" className="text-[11px]">{getRolLabel(rol)}</Badge>;
}

export interface EstadoSwitchProps {
  usuario: UsuarioAdmin;
  esPropioUsuario: boolean;
  onToggle: (u: UsuarioAdmin) => void;
}

export function EstadoSwitch({ usuario, esPropioUsuario, onToggle }: EstadoSwitchProps) {
  const activo = !usuario.eliminado_en;
  const dotColor = activo ? 'bg-success-600' : 'bg-error-600';

  // Sesión propia: badge estático coloreado (sin punto, sin borde, sin hover) — igual que Badge variant success/error del proyecto de referencia
  if (esPropioUsuario) {
    return (
      <span
        title="No podés cambiar tu propio estado"
        className={`inline-flex items-center font-medium rounded-full px-2.5 py-1 text-sm cursor-default select-none ${
          activo ? 'bg-success-50 text-success-700' : 'bg-error-50 text-error-700'
        }`}
      >
        {activo ? 'Activo' : 'Inactivo'}
      </span>
    );
  }

  return (
    <button
      type="button"
      aria-label={activo ? 'Activo — click para dar de baja' : 'Inactivo — click para reactivar'}
      onClick={() => onToggle(usuario)}
      className={`inline-flex items-center px-3 py-1.5 rounded-full text-xs font-semibold shadow-sm border transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-offset-1 ${
        activo
          ? 'bg-success-100 text-success-800 border-success-200 hover:bg-success-200 focus:ring-success-500'
          : 'bg-error-100 text-error-800 border-error-200 hover:bg-error-200 focus:ring-error-500'
      }`}
    >
      <span className={`w-2 h-2 rounded-full mr-2 ${dotColor}`} />
      {activo ? 'Activo' : 'Inactivo'}
    </button>
  );
}
