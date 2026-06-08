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
import { TextField } from '../ui/TextField';
import { ConfirmModal } from '../ui/ConfirmModal';
import { STAFF_NAV } from '../ui/nav';
import { useToast } from '../ui/toast';
import { api } from '../lib/api';
import type { UsuarioAdmin } from '../lib/types';

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
  roles: string;
}

const ROLES_VALIDOS = ['estudiante', 'proctor', 'admin_sistema'];

const FORM_VACIO: FormState = {
  id_institucional: '',
  email: '',
  nombre: '',
  apellido: '',
  password: '',
  roles: '',
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
      // Task 5.3: cargar fotos de perfil para cada usuario.
      for (const u of data.items) {
        if (!fotos[u.id]) {
          api.obtenerFotoPerfilDeUsuario(u.id).then((foto) => {
            if (foto) setFotos((prev) => ({ ...prev, [u.id]: foto }));
          });
        }
      }
    } catch {
      toast.error('No se pudo cargar la lista de usuarios.');
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
      roles: u.roles.join(', '),
    });
    setFormError(null);
  }

  function cerrarFormulario() {
    setModoForm(null);
    setEditando(null);
    setForm(FORM_VACIO);
    setFormError(null);
  }

  function cambiar(campo: keyof FormState) {
    return (e: React.ChangeEvent<HTMLInputElement>) =>
      setForm((prev) => ({ ...prev, [campo]: e.target.value }));
  }

  function parsearRoles(raw: string): string[] {
    return raw.split(',').map((r) => r.trim()).filter(Boolean);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);

    const roles = parsearRoles(form.roles);
    if (roles.length === 0) {
      setFormError('Ingresá al menos un rol válido.');
      return;
    }
    const invalidos = roles.filter((r) => !ROLES_VALIDOS.includes(r));
    if (invalidos.length > 0) {
      setFormError(`Roles inválidos: ${invalidos.join(', ')}. Válidos: ${ROLES_VALIDOS.join(', ')}.`);
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
      if (msg.includes('409') || msg.includes('409')) {
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
            <h1 className="font-headline text-headline-md text-on-surface tracking-tight">
              Gestión de usuarios
            </h1>
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
                    onChange={cambiar('id_institucional')}
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
                  onChange={cambiar('email')}
                  icon="email"
                  required
                  disabled={enviando}
                  placeholder="usuario@dominio.edu.ar"
                />
                <TextField
                  label="Nombre"
                  name="nombre"
                  value={form.nombre}
                  onChange={cambiar('nombre')}
                  icon="person"
                  disabled={enviando}
                  placeholder="Nombre"
                />
                <TextField
                  label="Apellido"
                  name="apellido"
                  value={form.apellido}
                  onChange={cambiar('apellido')}
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
                    onChange={cambiar('password')}
                    icon="lock"
                    required
                    disabled={enviando}
                    placeholder="Mínimo 8 caracteres"
                    hint="Mínimo 8 caracteres."
                  />
                )}
                <TextField
                  label="Roles (separados por coma)"
                  name="roles"
                  value={form.roles}
                  onChange={cambiar('roles')}
                  icon="manage_accounts"
                  required
                  disabled={enviando}
                  placeholder="estudiante, proctor, admin_sistema"
                  hint={`Roles válidos: ${ROLES_VALIDOS.join(', ')}.`}
                />
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
            <div className="mt-md space-y-base">
              {usuarios.map((u) => (
                <div
                  key={u.id}
                  className="flex items-center gap-md p-sm rounded-xl border border-outline-variant/30 hover:bg-surface-container-low transition-colors flex-wrap"
                >
                  {/* Avatar (task 5.3) */}
                  {fotos[u.id] ? (
                    <Avatar
                      src={fotos[u.id]}
                      alt={`Foto de ${u.nombre ?? u.email}`}
                      size={40}
                    />
                  ) : (
                    <div className="w-10 h-10 rounded-xl bg-secondary-container text-on-secondary flex items-center justify-center font-headline text-label-lg shrink-0">
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
                      {u.roles.join(', ')} · {u.auth_provider}
                    </p>
                  </div>

                  {/* Acciones */}
                  <div className="flex gap-xs shrink-0">
                    <Button
                      size="sm"
                      variant="outline"
                      icon="edit"
                      onClick={() => abrirEditar(u)}
                    >
                      Editar
                    </Button>
                    <Button
                      size="sm"
                      variant="danger"
                      icon="person_remove"
                      onClick={() => setABajar(u)}
                    >
                      Dar de baja
                    </Button>
                  </div>
                </div>
              ))}
            </div>
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
