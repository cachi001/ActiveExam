import { Icon, Card, SectionTitle, Button } from '../../../ui/components';
import { TextField } from '../../../ui/TextField';
import {
  ROL_LABELS,
  ROLES_FORMULARIO,
  type ModoFormulario,
  type FormState,
} from './UsuarioHelpers';
import { permisosPorModuloDeRol, CAPACIDAD_LABELS } from '../../../lib/capabilities';
import type { UsuarioAdmin } from '../../../lib/types';
import type { Rol } from '../../../lib/types';

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
  /** Solo en modo editar: si el formulario tiene algo distinto de lo cargado.
   *  Sin cambios, "Guardar cambios" queda deshabilitado. */
  hayCambios?: boolean;
  /** Editando la propia cuenta: nadie cambia su propio rol, ni siquiera la
   *  cuenta raíz — un cambio de privilegio no se auto-aprueba. El backend ya
   *  lo rechaza (409); esto evita que el intento llegue a mandarse. */
  esPropioUsuario?: boolean;
}

/** Permisos reales de un rol, agrupados por módulo/dominio (patrón copiado de
 * Sistema-de-Gestion-Convenios: un bloque por módulo, con label gris chico
 * arriba y las pills verdes de "permiso otorgado" debajo — agrupar por la
 * ENTIDAD sobre la que se actúa hace mucho más fácil entender de un vistazo
 * qué puede tocar cada rol que una lista plana). `estudiante` no tiene
 * ninguna capacidad declarada (todas son de staff) — se le muestra una frase
 * fija en vez de una lista vacía. */
function PermisosDeRol({ rol }: { rol: Rol }) {
  const grupos = permisosPorModuloDeRol(rol);
  if (grupos.length === 0) {
    return (
      <span className="block text-[12px] leading-snug text-on-surface-variant mt-1.5">
        Rinde exámenes. Solo ve lo suyo — no tiene permisos de gestión.
      </span>
    );
  }
  return (
    <div className="space-y-1.5 mt-1.5">
      {grupos.map(({ modulo, capacidades }) => (
        <div key={modulo}>
          <p className="text-[10px] font-semibold text-on-surface-variant/70 uppercase tracking-wider mb-1">
            {modulo}
          </p>
          <div className="flex flex-wrap gap-1">
            {capacidades.map((c) => (
              <span
                key={c}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] leading-snug bg-success-50 text-success-700"
              >
                <Icon name="check" className="text-[12px]" />
                {CAPACIDAD_LABELS[c]}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export function UsuarioFormPanel({
  modoForm, editando, form, formError, enviando,
  cambiarTexto, toggleRol, onSubmit, onCancelar, hayCambios = true,
  esPropioUsuario = false,
}: UsuarioFormPanelProps) {
  const rolDeshabilitado = enviando || esPropioUsuario;
  return (
    <Card>
      <SectionTitle>
        {modoForm === 'crear' ? 'Nuevo usuario' : 'Datos del usuario'}
      </SectionTitle>
      <form onSubmit={onSubmit} className="space-y-md mt-md">
        <div className="grid sm:grid-cols-2 gap-md">
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
          {modoForm === 'crear' ? (
            <TextField
              label="Usuario"
              name="username"
              value={form.username}
              onChange={cambiarTexto('username')}
              icon="badge"
              required
              disabled={enviando}
              placeholder="jperez"
              hint="Con esto inicia sesión. Solo letras, números, puntos, guiones y guiones bajos."
            />
          ) : (
            <TextField
              label="Usuario"
              name="username"
              value={editando?.username ?? ''}
              onChange={() => {}}
              icon="badge"
              disabled
              hint="No se puede cambiar desde acá — lo elige el usuario en su primer ingreso."
            />
          )}
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
        </div>

        <div>
          <p className="text-label-sm text-on-surface-variant mb-sm">Rol</p>
          {/* Una fila por rol con sus PERMISOS reales (no una descripción vaga):
              elegir un rol es decidir qué va a poder hacer esa persona, y quien lo
              elige tiene que ver la consecuencia concreta sin ir a leer el código.
              Selección ÚNICA (radio, no checkbox): un usuario tiene un solo rol —
              combinarlos rompe la separación entre quien pone la nota y quien
              decide el fraude. */}
          {esPropioUsuario && (
            <p className="text-body-sm text-on-surface-variant mb-sm">
              No podés cambiar tu propio rol — pedile a otro administrador que lo haga.
            </p>
          )}
          <div className="grid gap-sm sm:grid-cols-2 items-stretch">
            {ROLES_FORMULARIO.map((rol) => (
              <label
                key={rol}
                className={`flex h-full items-start gap-sm select-none rounded-md border border-surface-200 p-sm transition-colors ${
                  rolDeshabilitado ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer hover:bg-primary-50 hover:border-primary-200'
                }`}
              >
                <input
                  type="radio"
                  name="rol"
                  checked={form.roles[0] === rol}
                  onChange={() => toggleRol(rol)}
                  disabled={rolDeshabilitado}
                  className="w-6 h-6 accent-primary mt-0.5 shrink-0"
                />
                <span className="min-w-0">
                  <span className="block text-label-md text-on-surface">{ROL_LABELS[rol]}</span>
                  <PermisosDeRol rol={rol} />
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
          {/* Al editar, se habilita SOLO si hay algo distinto de lo que se cargó.
              Ofrecer guardar lo que no cambió invita a un PATCH inútil que igual
              audita, y borra la señal de si uno modificó algo — que es lo que uno
              quiere saber antes de confirmar cambios de roles sobre otra cuenta. */}
          <Button type="submit" disabled={enviando || (modoForm === 'editar' && !hayCambios)}>
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
