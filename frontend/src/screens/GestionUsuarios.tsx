/**
 * GestionUsuarios — CRUD administrativo de usuarios (C-61).
 *
 * Ruta: /admin/usuarios (roles: admin_sistema)
 * Accede a api.listarUsuarios / api.crearUsuario / api.editarUsuario /
 *         api.eliminarUsuario / api.reactivarUsuario (dual real/mock).
 *
 * Filtros server-side: rol, estado (activo/inactivo/todos), texto libre.
 * Estado como switch: verde=activo / rojo=inactivo, deshabilitado para el
 * propio usuario logueado (anti-lockout).
 */

import { useEffect, useState, useCallback } from 'react';
import { StaffShell } from '../ui/shells';
import { Icon, Card, SectionTitle, Badge, Button, Avatar } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { ActionMenu } from '../ui/ActionMenu';
import { TextField } from '../ui/TextField';
import { ConfirmModal } from '../ui/ConfirmModal';
import { STAFF_NAV } from '../ui/nav';
import { useToast } from '../ui/toast';
import { useNavigate } from '../lib/router';
import { useAuth } from '../lib/authStore';
import { api } from '../lib/api';
import type { UsuarioAdmin } from '../lib/types';
import { ROL_LABELS, ROLES_VALIDOS, getRolLabel } from '../lib/constants/roles';

/** Badge de rol — todos los roles con el MISMO color (primary), como el sistema
 * de referencia. El color del badge no distingue el rol; lo distingue el texto. */
function RolBadge({ rol }: { rol: string }) {
  return <Badge tone="primary" className="text-[11px]">{getRolLabel(rol)}</Badge>;
}

// ---------------------------------------------------------------------------
// Switch de estado (activo / inactivo)
// ---------------------------------------------------------------------------

interface EstadoSwitchProps {
  usuario: UsuarioAdmin;
  esPropioUsuario: boolean;
  onToggle: (u: UsuarioAdmin) => void;
}

function EstadoSwitch({ usuario, esPropioUsuario, onToggle }: EstadoSwitchProps) {
  const activo = !usuario.eliminado_en;
  const dotColor = activo ? 'bg-success-600' : 'bg-error-600';
  const tono = activo ? 'bg-success-100 text-success-800' : 'bg-error-100 text-error-800';

  // Tu propio usuario: no se puede cambiar el estado, así que NO se muestra como
  // botón (ni deshabilitado). Se muestra como un chip de estado PLANO (igual que
  // el sistema de referencia, que para isSelf renderiza un Badge, no el toggle).
  if (esPropioUsuario) {
    return (
      <span className={`inline-flex items-center px-3 py-1.5 rounded-full text-xs font-semibold ${tono}`}>
        <span className={`w-2 h-2 rounded-full mr-2 ${dotColor}`} />
        {activo ? 'Activo' : 'Inactivo'}
      </span>
    );
  }

  // Resto de usuarios: pill clickeable (estilo de la referencia) que alterna el estado.
  return (
    <button
      type="button"
      aria-label={activo ? 'Activo — click para dar de baja' : 'Inactivo — click para reactivar'}
      onClick={() => onToggle(usuario)}
      className={`inline-flex items-center px-3 py-1.5 rounded-full text-xs font-semibold shadow-sm border transition-colors duration-150 cursor-pointer focus:outline-none focus:ring-2 focus:ring-offset-1 ${
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

// Opciones de filtros
const OPCIONES_ROL = [
  { value: '', label: 'Todos los roles' },
  { value: 'admin_sistema', label: 'Administrador' },
  { value: 'proctor', label: 'Proctor' },
  { value: 'estudiante', label: 'Estudiante' },
];

const OPCIONES_ESTADO = [
  { value: 'activo', label: 'Activos' },
  { value: 'inactivo', label: 'Inactivos' },
  { value: 'todos', label: 'Todos' },
];

// ---------------------------------------------------------------------------
// Componente principal
// ---------------------------------------------------------------------------

export default function GestionUsuarios() {
  const toast = useToast();
  const navigate = useNavigate();
  const principal = useAuth((s) => s.principal);

  // Lista paginada
  const [usuarios, setUsuarios] = useState<UsuarioAdmin[]>([]);
  const [total, setTotal] = useState(0);
  const [cargando, setCargando] = useState(true);
  const PAGE_SIZE = 20;
  const [offset, setOffset] = useState(0);

  // Filtros server-side
  const [filtroRol, setFiltroRol] = useState('');
  const [filtroEstado, setFiltroEstado] = useState('activo');
  const [filtroQ, setFiltroQ] = useState('');
  // Valor del input de texto (diferido para debounce ligero)
  const [qInput, setQInput] = useState('');

  // Fotos de perfil indexadas por usuario_id
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

  const cargarUsuarios = useCallback(async (o: number, rol: string, estado: string, q: string) => {
    setCargando(true);
    try {
      const data = await api.listarUsuarios(PAGE_SIZE, o, {
        rol: rol || undefined,
        estado: estado !== 'todos' ? estado : undefined,
        q: q || undefined,
      });
      setUsuarios(data.items);
      setTotal(data.total);
      for (const u of data.items) {
        if (!fotos[u.id]) {
          api.obtenerFotoPerfilDeUsuario(u.id).then((foto) => {
            if (foto) setFotos((prev) => ({ ...prev, [u.id]: foto }));
          });
        }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes('401')) {
        toast.error('Tu sesión expiró. Cerrá sesión y volvé a entrar.');
      } else if (msg.includes('403')) {
        toast.error('No tenés permisos para listar usuarios.');
      } else {
        toast.error('No se pudo cargar la lista de usuarios.');
      }
    } finally {
      setCargando(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Carga inicial
  useEffect(() => { cargarUsuarios(0, filtroRol, filtroEstado, filtroQ); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Re-fetch al cambiar filtros de select (inmediato)
  function aplicarFiltros(rol: string, estado: string, q: string) {
    setOffset(0);
    cargarUsuarios(0, rol, estado, q);
  }

  function handleFiltroRol(v: string) {
    setFiltroRol(v);
    aplicarFiltros(v, filtroEstado, filtroQ);
  }

  function handleFiltroEstado(v: string) {
    setFiltroEstado(v);
    aplicarFiltros(filtroRol, v, filtroQ);
  }

  // Búsqueda de texto: debounce ligero (dispara al limpiar o al presionar Enter)
  function handleQChange(e: React.ChangeEvent<HTMLInputElement>) {
    const v = e.target.value;
    setQInput(v);
    if (!v) {
      setFiltroQ('');
      aplicarFiltros(filtroRol, filtroEstado, '');
    }
  }

  function handleQKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') {
      setFiltroQ(qInput);
      aplicarFiltros(filtroRol, filtroEstado, qInput);
    }
  }

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
      await cargarUsuarios(offset, filtroRol, filtroEstado, filtroQ);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes('409')) {
        setFormError('Ya existe un usuario con ese email o legajo, o no podés quitarte el rol de administrador.');
      } else {
        setFormError(`Error: ${msg}`);
      }
    } finally {
      setEnviando(false);
    }
  }

  // ---------------------------------------------------------------------------
  // Baja lógica y reactivación
  // ---------------------------------------------------------------------------

  async function handleBaja() {
    if (!aBajar) return;
    const u = aBajar;
    setABajar(null);
    try {
      await api.eliminarUsuario(u.id);
      toast.success(`${u.email} dado de baja.`);
      await cargarUsuarios(offset, filtroRol, filtroEstado, filtroQ);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes('409')) {
        toast.error('No podés darte de baja a vos mismo.');
      } else {
        toast.error(`Error al dar de baja: ${msg}`);
      }
    }
  }

  async function handleToggleEstado(u: UsuarioAdmin) {
    const activo = !u.eliminado_en;
    if (activo) {
      // Pedir confirmación antes de dar de baja
      setABajar(u);
    } else {
      // Reactivar sin confirmación
      try {
        await api.reactivarUsuario(u.id);
        toast.success(`${u.email} reactivado.`);
        await cargarUsuarios(offset, filtroRol, filtroEstado, filtroQ);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        toast.error(`No se pudo reactivar: ${msg}`);
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
    cargarUsuarios(nuevoOffset, filtroRol, filtroEstado, filtroQ);
  }

  function verDetalle(u: UsuarioAdmin) {
    navigate(`/admin/usuarios/${u.id}`);
  }

  // Identifica si un usuario es el propio usuario logueado (por email o id_institucional)
  function esPropioUsuario(u: UsuarioAdmin): boolean {
    if (!principal) return false;
    return u.email === principal.email || u.id_institucional === principal.id_institucional;
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <StaffShell
      nav={STAFF_NAV}
      title="Gestión de usuarios"
      subtitle="Alta, edición y baja lógica de usuarios de la plataforma."
      help={
        <HelpButton title="Gestión de usuarios">
          <p>
            Acá das de alta, editás y cambiás el estado de los usuarios. Solo visible para
            administradores del sistema.
          </p>
          <p>
            Los roles disponibles son <em>Estudiante</em>, <em>Proctor</em> y{' '}
            <em>Administrador</em>. La baja es lógica: el usuario no se borra,
            solo pierde acceso. La evidencia asociada queda intacta.
          </p>
          <p>
            No podés cambiar tu propio estado ni quitarte el rol de administrador.
          </p>
        </HelpButton>
      }
      actions={
        <Button icon="person_add" onClick={abrirCrear} size="sm">
          Nuevo usuario
        </Button>
      }
    >
      <div className="space-y-lg animate-in fade-in duration-500">

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

        {/* Card de filtros */}
        <Card>
          <SectionTitle sub="Filtrá por rol, estado o búsqueda de texto.">Filtros</SectionTitle>
          <div className="flex flex-col sm:flex-row gap-md mt-md flex-wrap">
            {/* Filtro de rol */}
            <div className="flex flex-col gap-xs min-w-[160px]">
              <label className="text-[11px] font-semibold text-on-surface-variant uppercase tracking-wide">
                Rol
              </label>
              <select
                value={filtroRol}
                onChange={(e) => handleFiltroRol(e.target.value)}
                className="text-[13px] rounded-lg border border-outline-variant/60 bg-surface-container-low px-3 py-1.5 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/30 text-on-surface"
              >
                {OPCIONES_ROL.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>

            {/* Filtro de estado */}
            <div className="flex flex-col gap-xs min-w-[140px]">
              <label className="text-[11px] font-semibold text-on-surface-variant uppercase tracking-wide">
                Estado
              </label>
              <select
                value={filtroEstado}
                onChange={(e) => handleFiltroEstado(e.target.value)}
                className="text-[13px] rounded-lg border border-outline-variant/60 bg-surface-container-low px-3 py-1.5 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/30 text-on-surface"
              >
                {OPCIONES_ESTADO.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>

            {/* Búsqueda de texto */}
            <div className="flex flex-col gap-xs flex-1 min-w-[200px]">
              <label className="text-[11px] font-semibold text-on-surface-variant uppercase tracking-wide">
                Buscar
              </label>
              <div className="relative">
                <Icon name="search" className="text-[16px] text-on-surface-variant absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                <input
                  type="search"
                  placeholder="Nombre, email o legajo… (Enter)"
                  value={qInput}
                  onChange={handleQChange}
                  onKeyDown={handleQKeyDown}
                  className="w-full pl-8 pr-3 py-1.5 text-[13px] rounded-lg border border-outline-variant/60 bg-surface-container-low focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/30 placeholder:text-on-surface-variant/60"
                />
              </div>
            </div>
          </div>
        </Card>

        {/* Tabla / listado de usuarios */}
        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/60 shadow-card overflow-hidden">
          <div className="px-4 py-3 border-b border-outline-variant/40 flex items-center gap-2">
            <Icon name="group" className="text-[16px] text-primary shrink-0" />
            <h2 className="text-[13px] font-semibold text-on-surface">
              Usuarios
              <span className="text-on-surface-variant font-normal ml-1">({total})</span>
            </h2>
          </div>

          {cargando ? (
            <div className="py-12 text-center text-on-surface-variant">
              <Icon name="progress_activity" className="ae-spin text-[28px] text-outline" />
            </div>
          ) : usuarios.length === 0 ? (
            <div className="py-12 text-center text-on-surface-variant space-y-base">
              <Icon name="group_off" className="text-[32px] text-outline" />
              <p className="text-[13px]">No se encontraron usuarios con esos filtros.</p>
            </div>
          ) : (
            <>
              {/* Tabla desktop (hidden en mobile) */}
              <div className="hidden md:block overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="bg-surface-container-low">
                      <th className="text-left text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-4 py-2.5">Nombre</th>
                      <th className="text-left text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-4 py-2.5">Email</th>
                      <th className="text-left text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-4 py-2.5">Legajo</th>
                      <th className="text-left text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-4 py-2.5">Roles</th>
                      <th className="text-left text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-4 py-2.5">Estado</th>
                      <th className="text-right text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-4 py-2.5">Acciones</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-outline-variant/30">
                    {usuarios.map((u) => (
                      <tr key={u.id} className="hover:bg-surface-container-low transition-colors group">
                        {/* Avatar + Nombre */}
                        <td className="px-4 py-3.5 whitespace-nowrap">
                          <div className="flex items-center gap-3">
                            {fotos[u.id] ? (
                              <Avatar src={fotos[u.id]} alt={`Foto de ${u.nombre ?? u.email}`} size={34} />
                            ) : (
                              <div className="w-8 h-8 rounded-full bg-secondary-container text-on-secondary flex items-center justify-center font-semibold text-[13px] shrink-0">
                                {(u.nombre ?? u.email).charAt(0).toUpperCase()}
                              </div>
                            )}
                            <button
                              type="button"
                              onClick={() => verDetalle(u)}
                              className="text-[13px] font-semibold text-on-surface group-hover:text-primary transition-colors truncate max-w-[180px] text-left"
                            >
                              {u.nombre && u.apellido
                                ? `${u.nombre} ${u.apellido}`
                                : u.nombre ?? u.apellido ?? u.email}
                            </button>
                          </div>
                        </td>
                        <td className="px-4 py-3.5 whitespace-nowrap text-[13px] text-on-surface-variant truncate max-w-[220px]">
                          {u.email}
                        </td>
                        <td className="px-4 py-3.5 whitespace-nowrap">
                          <span className="font-mono text-[12px] text-on-surface-variant bg-surface-container px-2 py-0.5 rounded-md">
                            {u.id_institucional}
                          </span>
                        </td>
                        <td className="px-4 py-3.5 whitespace-nowrap">
                          <div className="flex flex-wrap gap-1">
                            {u.roles.map((r) => <RolBadge key={r} rol={r} />)}
                          </div>
                        </td>
                        <td className="px-4 py-3.5 whitespace-nowrap">
                          <EstadoSwitch
                            usuario={u}
                            esPropioUsuario={esPropioUsuario(u)}
                            onToggle={handleToggleEstado}
                          />
                        </td>
                        <td className="px-4 py-3.5 whitespace-nowrap text-right">
                          <ActionMenu
                            ariaLabel={`Acciones de ${u.email}`}
                            items={[
                              { label: 'Ver detalle', icon: 'person_search', onClick: () => verDetalle(u) },
                              { label: 'Editar', icon: 'edit', onClick: () => abrirEditar(u) },
                            ]}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Cards mobile (hidden en desktop) */}
              <div className="md:hidden divide-y divide-outline-variant/30">
                {usuarios.map((u) => (
                  <div key={u.id} className="px-4 py-4 flex items-start gap-3">
                    {fotos[u.id] ? (
                      <Avatar src={fotos[u.id]} alt={`Foto de ${u.nombre ?? u.email}`} size={40} />
                    ) : (
                      <div className="w-10 h-10 rounded-full bg-secondary-container text-on-secondary flex items-center justify-center font-semibold text-[14px] shrink-0">
                        {(u.nombre ?? u.email).charAt(0).toUpperCase()}
                      </div>
                    )}
                    <div className="flex-1 min-w-0">
                      <button
                        type="button"
                        onClick={() => verDetalle(u)}
                        className="text-[13px] font-semibold text-on-surface hover:text-primary transition-colors truncate text-left w-full"
                      >
                        {u.nombre && u.apellido
                          ? `${u.nombre} ${u.apellido}`
                          : u.nombre ?? u.apellido ?? u.email}
                      </button>
                      <p className="text-[11px] text-on-surface-variant truncate mt-0.5">
                        {u.email}
                      </p>
                      <p className="text-[11px] font-mono text-on-surface-variant mt-0.5">
                        {u.id_institucional}
                      </p>
                      <div className="flex flex-wrap gap-1 mt-1.5">
                        {u.roles.map((r) => <RolBadge key={r} rol={r} />)}
                      </div>
                      {/* Estado visible en mobile */}
                      <div className="mt-2">
                        <EstadoSwitch
                          usuario={u}
                          esPropioUsuario={esPropioUsuario(u)}
                          onToggle={handleToggleEstado}
                        />
                      </div>
                    </div>
                    <ActionMenu
                      ariaLabel="Acciones del usuario"
                      items={[
                        { label: 'Ver detalle', icon: 'person_search', onClick: () => verDetalle(u) },
                        { label: 'Editar', icon: 'edit', onClick: () => abrirEditar(u) },
                      ]}
                    />
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Paginación */}
          {totalPaginas > 1 && (
            <div className="px-4 py-3 flex items-center justify-between border-t border-outline-variant/40">
              <Button
                size="sm"
                variant="ghost"
                icon="chevron_left"
                disabled={paginaActual <= 1}
                onClick={() => irPagina(paginaActual - 1)}
              >
                Anterior
              </Button>
              <span className="text-[11px] text-on-surface-variant">
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
        </div>

      </div>

      {/* Modal de confirmación de baja */}
      <ConfirmModal
        abierto={aBajar !== null}
        variante="danger"
        titulo="Dar de baja al usuario"
        mensaje={
          aBajar ? (
            <>
              ¿Confirmar la baja de <strong>{aBajar.email}</strong>?
              <br />
              <span className="text-on-surface-variant text-body-sm">
                El usuario no podrá iniciar sesión. La evidencia generada queda intacta.
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
