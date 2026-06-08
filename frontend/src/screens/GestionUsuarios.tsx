/**
 * GestionUsuarios — CRUD administrativo de usuarios (C-61).
 *
 * Ruta: /admin/usuarios (roles: admin_sistema)
 * Accede a api.listarUsuarios / api.crearUsuario / api.editarUsuario / api.eliminarUsuario
 * (dual real/mock).
 *
 * Reglas:
 * - Anti-lockout: el backend rechaza que el admin se quite el rol admin_sistema (409).
 * - Baja lógica (soft-delete): el usuario no se borra físicamente.
 * - Evidencia intacta tras la baja (L2.5).
 * - La tabla muestra avatar (foto de perfil) si está disponible (C-61 task 5.3).
 */

import { useEffect, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Icon, Card, SectionTitle, Button, Avatar } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { TextField } from '../ui/TextField';
import { ConfirmModal } from '../ui/ConfirmModal';
import { STAFF_NAV } from '../ui/nav';
import { useToast } from '../ui/toast';
import { api } from '../lib/api';
import type { UsuarioAdmin } from '../lib/types';
import { ROL_LABELS, ROLES_VALIDOS, getRolLabel } from '../lib/constants/roles';

// ---------------------------------------------------------------------------
// Tipos locales
// ---------------------------------------------------------------------------

type ModoFormulario = 'crear' | 'editar';

interface FormState {
  id_institucional: string;
  email: string;
  nombre: string;
  apellido: string;
  password: string;
  roles: string[];
}

const FORM_VACIO: FormState = {
  id_institucional: '',
  email: '',
  nombre: '',
  apellido: '',
  password: '',
  roles: [],
};

// ---------------------------------------------------------------------------
// Componente principal
// ---------------------------------------------------------------------------

export default function GestionUsuarios() {
  const toast = useToast();

  // Lista paginada
  const [usuarios, setUsuarios] = useState<UsuarioAdmin[]>([]);
  const [total, setTotal] = useState(0);
  const [cargando, setCargando] = useState(true);
  const PAGE_SIZE = 20;
  const [offset, setOffset] = useState(0);

  // Fotos de perfil indexadas por usuario_id (cargadas bajo demanda — task 5.3)
  const [fotos, setFotos] = useState<Record<string, string>>({});

  // Formulario de creación / edición
  const [modoForm, setModoForm] = useState<ModoFormulario | null>(null);
  const [editando, setEditando] = useState<UsuarioAdmin | null>(null);
  const [form, setForm] = useState<FormState>(FORM_VACIO);
  const [formError, setFormError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  // Modal de confirmación de baja
  const [aBajar, setABajar] = useState<UsuarioAdmin | null>(null);

  // ---------------------------------------------------------------------------
  // Carga de datos
  // ---------------------------------------------------------------------------

  const cargarUsuarios = async (o = offset) => {
    setCargando(true);
    try {
      const data = await api.listarUsuarios(PAGE_SIZE, o);
      setUsuarios(data.items);
      setTotal(data.total);
      // Task 5.3: cargar fotos de perfil para cada usuario. Solo intenta una vez
      // por usuario por carga; los 404 (sin foto vigente) son normales y se
      // ignoran silenciosamente.
      for (const u of data.items) {
        if (!fotos[u.id]) {
          api.obtenerFotoPerfilDeUsuario(u.id).then((foto) => {
            if (foto) setFotos((prev) => ({ ...prev, [u.id]: foto }));
          });
        }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      // 401 = sesión vencida o sin rol admin_sistema → mensaje accionable.
      // 403 = autenticado pero sin permisos suficientes.
      if (msg.includes('401')) {
        toast.error('Tu sesión expiró. Cerrá sesión y volvé a entrar.');
      } else if (msg.includes('403')) {
        toast.error('No tenés permisos para listar usuarios (requiere admin_sistema).');
      } else {
        toast.error('No se pudo cargar la lista de usuarios.');
      }
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => { cargarUsuarios(0); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ---------------------------------------------------------------------------
  // Formulario
  // ---------------------------------------------------------------------------

  function abrirCrear() {
    setModoForm('crear');
    setEditando(null);
    setForm(FORM_VACIO);
    setFormError(null);
  }

  function abrirEditar(u: UsuarioAdmin) {
    setModoForm('editar');
    setEditando(u);
    setForm({
      id_institucional: u.id_institucional,
      email: u.email,
      nombre: u.nombre ?? '',
      apellido: u.apellido ?? '',
      password: '',
      roles: [...u.roles],
    });
    setFormError(null);
  }

  function cerrarFormulario() {
    setModoForm(null);
    setEditando(null);
    setForm(FORM_VACIO);
    setFormError(null);
  }

  function cambiarTexto(campo: keyof Omit<FormState, 'roles'>) {
    return (e: React.ChangeEvent<HTMLInputElement>) =>
      setForm((prev) => ({ ...prev, [campo]: e.target.value }));
  }

  function toggleRol(rol: string) {
    setForm((prev) => {
      const existe = prev.roles.includes(rol);
      return {
        ...prev,
        roles: existe ? prev.roles.filter((r) => r !== rol) : [...prev.roles, rol],
      };
    });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);

    const roles = form.roles;
    if (roles.length === 0) {
      setFormError('Seleccioná al menos un rol.');
      return;
    }

    setEnviando(true);
    try {
      if (modoForm === 'crear') {
        if (form.password.length < 8) {
          setFormError('La contraseña debe tener al menos 8 caracteres.');
          return;
        }
        await api.crearUsuario({
          id_institucional: form.id_institucional,
          email: form.email,
          password: form.password,
          roles,
          nombre: form.nombre || undefined,
          apellido: form.apellido || undefined,
        });
        toast.success('Usuario creado correctamente.');
      } else if (modoForm === 'editar' && editando) {
        await api.editarUsuario(editando.id, {
          email: form.email || undefined,
          nombre: form.nombre || undefined,
          apellido: form.apellido || undefined,
          roles,
        });
        toast.success('Usuario actualizado correctamente.');
      }
      cerrarFormulario();
      await cargarUsuarios(offset);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes('409')) {
        setFormError('Ya existe un usuario con ese email o id_institucional, o no podés quitarte el rol admin_sistema.');
      } else {
        setFormError(`Error: ${msg}`);
      }
    } finally {
      setEnviando(false);
    }
  }

  // ---------------------------------------------------------------------------
  // Baja lógica
  // ---------------------------------------------------------------------------

  async function handleBaja() {
    if (!aBajar) return;
    const u = aBajar;
    setABajar(null);
    try {
      await api.eliminarUsuario(u.id);
      toast.success(`Usuario ${u.email} dado de baja correctamente.`);
      await cargarUsuarios(offset);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes('409')) {
        toast.error('No podés darte de baja a vos mismo.');
      } else {
        toast.error(`Error al dar de baja: ${msg}`);
      }
    }
  }

  // ---------------------------------------------------------------------------
  // Paginación
  // ---------------------------------------------------------------------------

  const totalPaginas = Math.ceil(total / PAGE_SIZE);
  const paginaActual = Math.floor(offset / PAGE_SIZE) + 1;

  function irPagina(p: number) {
    const nuevoOffset = (p - 1) * PAGE_SIZE;
    setOffset(nuevoOffset);
    cargarUsuarios(nuevoOffset);
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <StaffShell nav={STAFF_NAV} title="Gestión de usuarios">
      <div className="space-y-lg animate-in fade-in duration-500">

        {/* Encabezado */}
        <div className="flex items-start justify-between gap-md flex-wrap">
          <div>
            <div className="flex items-center gap-sm">
              <h1 className="font-headline text-headline-md text-on-surface tracking-tight">
                Gestión de usuarios
              </h1>
              <HelpButton title="Gestión de usuarios">
                <p>
                  Acá das de alta, editás y das de baja a los usuarios de la plataforma. Solo
                  visible para <strong>admin_sistema</strong>.
                </p>
                <p>
                  Los roles MVP son tres estrictos: <em>estudiante</em>, <em>proctor</em> y
                  <em> admin_sistema</em>. La baja es <strong>lógica</strong> (no destruye evidencia)
                  y revoca los refresh tokens del usuario.
                </p>
                <p>
                  Anti-lockout: no podés quitarte a vos mismo el rol admin_sistema ni darte de baja.
                </p>
              </HelpButton>
            </div>
            <p className="text-body-md text-on-surface-variant mt-base">
              Alta, edición y baja lógica de usuarios de la plataforma.
            </p>
          </div>
          <Button icon="person_add" onClick={abrirCrear} size="md">
            Nuevo usuario
          </Button>
        </div>

        {/* Formulario de creación / edición */}
        {modoForm && (
          <Card>
            <SectionTitle>
              {modoForm === 'crear' ? 'Nuevo usuario' : `Editar: ${editando?.email}`}
            </SectionTitle>
            <form onSubmit={handleSubmit} className="space-y-md mt-md">
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

              {/* Selector de roles por checkboxes */}
              <div>
                <p className="text-label-sm text-on-surface-variant mb-sm">Roles</p>
                <div className="flex flex-wrap gap-md">
                  {ROLES_VALIDOS.map((rol) => (
                    <label key={rol} className="flex items-center gap-xs cursor-pointer select-none">
                      <input
                        type="checkbox"
                        checked={form.roles.includes(rol)}
                        onChange={() => toggleRol(rol)}
                        disabled={enviando}
                        className="w-4 h-4 accent-primary"
                      />
                      <span className="text-label-md text-on-surface">{ROL_LABELS[rol]}</span>
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
                <Button type="button" variant="ghost" onClick={cerrarFormulario} disabled={enviando}>
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
        )}

        {/* Tabla / listado de usuarios */}
        <Card>
          <SectionTitle sub={`${total} usuario${total !== 1 ? 's' : ''} activos`}>
            Usuarios activos
          </SectionTitle>

          {cargando ? (
            <div className="py-xl text-center text-on-surface-variant">
              <Icon name="progress_activity" className="ae-spin text-[36px] text-outline" />
            </div>
          ) : usuarios.length === 0 ? (
            <div className="py-xl text-center text-on-surface-variant space-y-base">
              <Icon name="group_off" className="text-[36px] text-outline" />
              <p className="text-label-md">No hay usuarios activos.</p>
            </div>
          ) : (
            <>
              {/* Tabla desktop (hidden en mobile) */}
              <table className="hidden md:table w-full mt-md border-collapse">
                <thead>
                  <tr className="border-b border-outline-variant/30">
                    <th className="text-left text-label-sm text-on-surface-variant font-medium py-sm pr-md">Avatar / Nombre</th>
                    <th className="text-left text-label-sm text-on-surface-variant font-medium py-sm pr-md">Email</th>
                    <th className="text-left text-label-sm text-on-surface-variant font-medium py-sm pr-md">Legajo</th>
                    <th className="text-left text-label-sm text-on-surface-variant font-medium py-sm pr-md">Rol</th>
                    <th className="text-right text-label-sm text-on-surface-variant font-medium py-sm">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {usuarios.map((u) => (
                    <tr key={u.id} className="border-b border-outline-variant/20 hover:bg-surface-container-low transition-colors">
                      {/* Avatar + Nombre */}
                      <td className="py-sm pr-md">
                        <div className="flex items-center gap-sm">
                          {fotos[u.id] ? (
                            <Avatar src={fotos[u.id]} alt={`Foto de ${u.nombre ?? u.email}`} size={36} />
                          ) : (
                            <div className="w-9 h-9 rounded-md bg-secondary-container text-on-secondary flex items-center justify-center font-headline text-label-md shrink-0">
                              {(u.nombre ?? u.email).charAt(0).toUpperCase()}
                            </div>
                          )}
                          <span className="text-label-md font-semibold text-on-surface truncate max-w-[160px]">
                            {u.nombre && u.apellido
                              ? `${u.nombre} ${u.apellido}`
                              : u.nombre ?? u.apellido ?? u.email}
                          </span>
                        </div>
                      </td>
                      {/* Email */}
                      <td className="py-sm pr-md text-label-sm text-on-surface-variant truncate max-w-[200px]">
                        {u.email}
                      </td>
                      {/* Legajo */}
                      <td className="py-sm pr-md text-label-sm text-on-surface-variant">
                        {u.id_institucional}
                      </td>
                      {/* Roles */}
                      <td className="py-sm pr-md text-label-sm text-on-surface-variant">
                        {u.roles.map((r) => getRolLabel(r)).join(', ')}
                      </td>
                      {/* Acciones */}
                      <td className="py-sm text-right">
                        <div className="flex gap-xs justify-end">
                          <Button size="sm" variant="outline" icon="edit" onClick={() => abrirEditar(u)}>
                            Editar
                          </Button>
                          <Button size="sm" variant="danger" icon="person_remove" onClick={() => setABajar(u)}>
                            Dar de baja
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* Cards mobile (hidden en desktop) */}
              <div className="md:hidden mt-md space-y-base">
                {usuarios.map((u) => (
                  <div
                    key={u.id}
                    className="bg-white border border-outline-variant/30 shadow-sm rounded-md p-sm flex items-center gap-md flex-wrap"
                  >
                    {/* Avatar */}
                    {fotos[u.id] ? (
                      <Avatar src={fotos[u.id]} alt={`Foto de ${u.nombre ?? u.email}`} size={40} />
                    ) : (
                      <div className="w-10 h-10 rounded-md bg-secondary-container text-on-secondary flex items-center justify-center font-headline text-label-lg shrink-0">
                        {(u.nombre ?? u.email).charAt(0).toUpperCase()}
                      </div>
                    )}

                    {/* Datos */}
                    <div className="flex-1 min-w-0">
                      <p className="text-label-md font-semibold text-on-surface truncate">
                        {u.nombre && u.apellido
                          ? `${u.nombre} ${u.apellido}`
                          : u.nombre ?? u.apellido ?? u.email}
                      </p>
                      <p className="text-label-sm text-on-surface-variant truncate">
                        {u.email} · {u.id_institucional}
                      </p>
                      <p className="text-label-sm text-on-surface-variant">
                        {u.roles.map((r) => getRolLabel(r)).join(', ')}
                      </p>
                    </div>

                    {/* Acciones */}
                    <div className="flex gap-xs shrink-0">
                      <Button size="sm" variant="outline" icon="edit" onClick={() => abrirEditar(u)}>
                        Editar
                      </Button>
                      <Button size="sm" variant="danger" icon="person_remove" onClick={() => setABajar(u)}>
                        Dar de baja
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Paginación */}
          {totalPaginas > 1 && (
            <div className="flex items-center justify-between mt-lg pt-md border-t border-outline-variant/30">
              <Button
                size="sm"
                variant="ghost"
                icon="chevron_left"
                disabled={paginaActual <= 1}
                onClick={() => irPagina(paginaActual - 1)}
              >
                Anterior
              </Button>
              <span className="text-label-sm text-on-surface-variant">
                Página {paginaActual} de {totalPaginas}
              </span>
              <Button
                size="sm"
                variant="ghost"
                iconRight="chevron_right"
                disabled={paginaActual >= totalPaginas}
                onClick={() => irPagina(paginaActual + 1)}
              >
                Siguiente
              </Button>
            </div>
          )}
        </Card>

      </div>

      {/* Modal de confirmación de baja */}
      <ConfirmModal
        abierto={aBajar !== null}
        variante="danger"
        titulo="Dar de baja al usuario"
        mensaje={
          aBajar ? (
            <>
              ¿Confirmar la baja lógica de <strong>{aBajar.email}</strong>?
              <br />
              <span className="text-on-surface-variant text-body-sm">
                El usuario no podrá iniciar sesión. La evidencia queda intacta (cadena de custodia).
              </span>
            </>
          ) : null
        }
        textoConfirmar="Dar de baja"
        textoCancelar="Cancelar"
        onConfirmar={handleBaja}
        onCancelar={() => setABajar(null)}
      />
    </StaffShell>
  );
}
