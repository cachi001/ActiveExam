import { Icon, Card, SectionTitle, Button } from '../../../ui/components';
import { TextField } from '../../../ui/TextField';
import {
  ROL_DESCRIPCIONES,
  ROL_LABELS,
  ROLES_VALIDOS,
  type ModoFormulario,
  type FormState,
} from './UsuarioHelpers';
import type { UsuarioAdmin } from '../../../lib/types';

interface UsuarioFormPanelProps {
  modoForm: ModoFormulario;
  editando: UsuarioAdmin | null;
  form: FormState;
  formError: string | null;
  enviando: boolean;
  cambiarTexto: (campo: keyof Omit<FormState, 'roles'>) => (e: React.ChangeEvent<HTMLInputElement>) => void;
  toggleRol: (rol: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  onCancelar: () => void;
}

export function UsuarioFormPanel({
  modoForm, editando, form, formError, enviando,
  cambiarTexto, toggleRol, onSubmit, onCancelar,
}: UsuarioFormPanelProps) {
  return (
    <Card>
      <SectionTitle>
        {modoForm === 'crear' ? 'Nuevo usuario' : `Editar: ${editando?.email}`}
      </SectionTitle>
      <form onSubmit={onSubmit} className="space-y-md mt-md">
        <div className="grid sm:grid-cols-2 gap-md">
          {modoForm === 'crear' && (
            <TextField
              label="ID institucional"
              name="id_institucional"
              value={form.id_institucional}
              onChange={cambiarTexto('id_institucional')}
              icon="badge"
              required
              disabled={enviando}
              placeholder="FRM-23-4912"
            />
          )}
          <TextField
            label="Email"
            name="email"
            type="email"
            value={form.email}
            onChange={cambiarTexto('email')}
            icon="email"
            required
            disabled={enviando}
            placeholder="usuario@dominio.edu.ar"
          />
          <TextField
            label="Nombre"
            name="nombre"
            value={form.nombre}
            onChange={cambiarTexto('nombre')}
            icon="person"
            disabled={enviando}
            placeholder="Nombre"
          />
          <TextField
            label="Apellido"
            name="apellido"
            value={form.apellido}
            onChange={cambiarTexto('apellido')}
            icon="person"
            disabled={enviando}
            placeholder="Apellido"
          />
          {modoForm === 'crear' && (
            <TextField
              label="Contraseña"
              name="password"
              type="password"
              value={form.password}
              onChange={cambiarTexto('password')}
              icon="lock"
              required
              disabled={enviando}
              placeholder="Mínimo 8 caracteres"
              hint="Mínimo 8 caracteres."
            />
          )}
        </div>

        <div>
          <p className="text-label-sm text-on-surface-variant mb-sm">Roles</p>
          {/* Una fila por rol con su descripción: elegir un rol es decidir qué va a
              poder hacer esa persona, y quien lo elige tiene que ver la consecuencia
              sin ir a leer el código. En grilla de 2 para que no quede una lista larga. */}
          <div className="grid gap-sm sm:grid-cols-2 items-stretch">
            {ROLES_VALIDOS.map((rol) => (
              <label
                key={rol}
                className="flex h-full items-start gap-sm cursor-pointer select-none rounded-md border border-surface-200 p-sm hover:bg-primary-50 hover:border-primary-200 transition-colors"
              >
                <input
                  type="checkbox"
                  checked={form.roles.includes(rol)}
                  onChange={() => toggleRol(rol)}
                  disabled={enviando}
                  className="w-4 h-4 accent-primary mt-0.5 shrink-0"
                />
                <span className="min-w-0">
                  <span className="block text-label-md text-on-surface">{ROL_LABELS[rol]}</span>
                  <span className="block text-[12px] leading-snug text-on-surface-variant mt-0.5">
                    {ROL_DESCRIPCIONES[rol]}
                  </span>
                </span>
              </label>
            ))}
          </div>
        </div>

        {formError && (
          <div className="flex items-center gap-xs text-error text-body-sm p-sm rounded-lg bg-error-container">
            <Icon name="error" className="text-[18px] shrink-0" fill />
            {formError}
          </div>
        )}

        <div className="flex gap-sm justify-end">
          <Button type="button" variant="ghost" onClick={onCancelar} disabled={enviando}>
            Cancelar
          </Button>
          <Button type="submit" disabled={enviando}>
            {enviando ? (
              <span className="inline-flex items-center gap-xs">
                <Icon name="progress_activity" className="ae-spin text-[20px]" />
                Guardando…
              </span>
            ) : modoForm === 'crear' ? 'Crear usuario' : 'Guardar cambios'}
          </Button>
        </div>
      </form>
    </Card>
  );
}
