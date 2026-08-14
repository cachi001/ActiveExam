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

import { useEffect, useState, useCallback, useRef } from 'react';
import { StaffShell } from '../ui/shells';
import { Button } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { ConfirmModal } from '../ui/ConfirmModal';
import { RefreshBar } from '../ui/RefreshBar';
import { STAFF_NAV } from '../ui/nav';
import { useAutoRefresh } from '../lib/useAutoRefresh';
import { useToast } from '../ui/toast';
import { useNavigate } from '../lib/router';
import { useAuth } from '../lib/authStore';
import { api } from '../lib/api';
import type { UsuarioAdmin } from '../lib/types';
import { FORM_VACIO, OPCIONES_ROL, OPCIONES_ESTADO, type ModoFormulario, type FormState } from './admin/components/UsuarioHelpers';
import { UsuarioFormPanel } from './admin/components/UsuarioFormPanel';
import { UsuarioTable } from './admin/components/UsuarioTable';
import { FiltrosPanel } from '../ui/FiltrosPanel';
import { Pagination, PageSizeSelect } from '../ui/Pagination';

export default function GestionUsuarios() {
  const toast = useToast();
  const navigate = useNavigate();
  const principal = useAuth((s) => s.principal);

  const [usuarios, setUsuarios] = useState<UsuarioAdmin[]>([]);
  const [total, setTotal] = useState(0);
  const [cargando, setCargando] = useState(true);
  const [pageSize, setPageSize] = useState(5);
  // Ref siempre-actual del pageSize para que cargarUsuarios (useCallback estable)
  // lea el valor vigente sin tener que pasarlo por cada call-site.
  const pageSizeRef = useRef(pageSize);
  pageSizeRef.current = pageSize;
  const [offset, setOffset] = useState(0);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | undefined>();

  // Aplicado (lo que se busca) vs borrador (lo que se edita en el panel).
  const [filtroRol, setFiltroRol] = useState('');
  const [filtroEstado, setFiltroEstado] = useState('todos');
  const [filtroQ, setFiltroQ] = useState('');
  const [borrRol, setBorrRol] = useState('');
  const [borrEstado, setBorrEstado] = useState('todos');
  const [borrQ, setBorrQ] = useState('');

  const [fotos, setFotos] = useState<Record<string, string>>({});

  const [modoForm, setModoForm] = useState<ModoFormulario | null>(null);
  const [editando, setEditando] = useState<UsuarioAdmin | null>(null);
  const [form, setForm] = useState<FormState>(FORM_VACIO);
  const [formError, setFormError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const [aBajar, setABajar] = useState<UsuarioAdmin | null>(null);

  const cargarUsuarios = useCallback(async (o: number, rol: string, estado: string, q: string) => {
    setCargando(true);
    try {
      const data = await api.listarUsuarios(pageSizeRef.current, o, {
        rol: rol || undefined,
        estado: estado !== 'todos' ? estado : undefined,
        q: q || undefined,
      });
      setUsuarios(data.items);
      setTotal(data.total);
      setLastUpdatedAt(Date.now());
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

  useEffect(() => { cargarUsuarios(0, filtroRol, filtroEstado, filtroQ); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-refresh cada 5 min conservando página y filtros actuales.
  useAutoRefresh(() => cargarUsuarios(offset, filtroRol, filtroEstado, filtroQ), undefined, !cargando);

  const hayCambiosFiltros =
    borrRol !== filtroRol || borrEstado !== filtroEstado || borrQ.trim() !== filtroQ;
  const hayFiltrosActivos = Boolean(borrRol) || borrEstado !== 'activo' || Boolean(borrQ);

  function aplicarFiltros() {
    const q = borrQ.trim();
    setFiltroRol(borrRol);
    setFiltroEstado(borrEstado);
    setFiltroQ(q);
    setOffset(0);
    cargarUsuarios(0, borrRol, borrEstado, q);
  }

  function limpiarFiltros() {
    setBorrRol('');
    setBorrEstado('activo');
    setBorrQ('');
    setFiltroRol('');
    setFiltroEstado('activo');
    setFiltroQ('');
    setOffset(0);
    cargarUsuarios(0, '', 'activo', '');
  }

  function abrirCrear() {
    setModoForm('crear'); setEditando(null); setForm(FORM_VACIO); setFormError(null);
  }

  function abrirEditar(u: UsuarioAdmin) {
    setModoForm('editar');
    setEditando(u);
    setForm({ id_institucional: u.id_institucional, email: u.email, nombre: u.nombre ?? '', apellido: u.apellido ?? '', password: '', roles: [...u.roles] });
    setFormError(null);
  }

  function cerrarFormulario() {
    setModoForm(null); setEditando(null); setForm(FORM_VACIO); setFormError(null);
  }

  function cambiarTexto(campo: keyof Omit<FormState, 'roles'>) {
    return (e: React.ChangeEvent<HTMLInputElement>) => setForm((prev) => ({ ...prev, [campo]: e.target.value }));
  }

  function toggleRol(rol: string) {
    setForm((prev) => {
      const existe = prev.roles.includes(rol);
      return { ...prev, roles: existe ? prev.roles.filter((r) => r !== rol) : [...prev.roles, rol] };
    });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    const roles = form.roles;
    if (roles.length === 0) { setFormError('Seleccioná al menos un rol.'); return; }
    setEnviando(true);
    try {
      if (modoForm === 'crear') {
        if (form.password && form.password.length < 8) { setFormError('La contraseña debe tener al menos 8 caracteres.'); return; }
        const resp = await api.crearUsuario({ id_institucional: form.id_institucional, email: form.email, password: form.password || undefined, roles, nombre: form.nombre || undefined, apellido: form.apellido || undefined });
        // La clave temporal NO se muestra aquí; el flujo de alta fue movido a /admin/usuarios/nuevo.
        // Este bloque sólo queda como fallback para la edición de flujos legacy inline (modo crear inline).
        if (!resp.password_generada) {
          toast.success('Usuario creado correctamente.');
        }
      } else if (modoForm === 'editar' && editando) {
        await api.editarUsuario(editando.id, { email: form.email || undefined, nombre: form.nombre || undefined, apellido: form.apellido || undefined, roles });
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
      if (msg.includes('409')) { toast.error('No podés darte de baja a vos mismo.'); }
      else { toast.error(`Error al dar de baja: ${msg}`); }
    }
  }

  async function handleToggleEstado(u: UsuarioAdmin) {
    const activo = !u.eliminado_en;
    if (activo) {
      setABajar(u);
    } else {
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

  const totalPaginas = Math.ceil(total / pageSize);
  const paginaActual = Math.floor(offset / pageSize) + 1;

  function irPagina(p: number) {
    const nuevoOffset = (p - 1) * pageSize;
    setOffset(nuevoOffset);
    cargarUsuarios(nuevoOffset, filtroRol, filtroEstado, filtroQ);
  }

  function cambiarPageSize(size: number) {
    pageSizeRef.current = size;
    setPageSize(size);
    setOffset(0);
    cargarUsuarios(0, filtroRol, filtroEstado, filtroQ);
  }

  function esPropioUsuario(u: UsuarioAdmin): boolean {
    if (!principal) return false;
    return u.email === principal.email || u.id_institucional === principal.id_institucional;
  }

  return (
    <StaffShell
      nav={STAFF_NAV}
      title="Gestión de usuarios"
      subtitle="Alta, edición y baja lógica de usuarios de la plataforma."
      help={
        <HelpButton title="Gestión de usuarios">
          <p>Acá das de alta, editás y cambiás el estado de los usuarios. Solo visible para administradores del sistema.</p>
          <p>Los roles disponibles son <em>Estudiante</em>, <em>Proctor</em> y <em>Administrador</em>. La baja es lógica: el usuario no se borra, solo pierde acceso. La evidencia asociada queda intacta.</p>
          <p>No podés cambiar tu propio estado ni quitarte el rol de administrador.</p>
        </HelpButton>
      }
      actions={<Button icon="person_add" onClick={() => navigate('/admin/usuarios/nuevo')} size="sm">Nuevo usuario</Button>}
    >
      <div className="space-y-lg animate-in fade-in duration-500">
        <RefreshBar
          texto="Gestión de usuarios"
          lastUpdatedAt={lastUpdatedAt}
          cargando={cargando}
          onActualizar={() => cargarUsuarios(offset, filtroRol, filtroEstado, filtroQ)}
        />
        {modoForm && (
          <UsuarioFormPanel
            modoForm={modoForm}
            editando={editando}
            form={form}
            formError={formError}
            enviando={enviando}
            cambiarTexto={cambiarTexto}
            toggleRol={toggleRol}
            onSubmit={handleSubmit}
            onCancelar={cerrarFormulario}
          />
        )}

        <FiltrosPanel
          onAplicar={aplicarFiltros}
          onLimpiar={limpiarFiltros}
          hayFiltros={hayFiltrosActivos}
          hayCambios={hayCambiosFiltros}
          aplicarDeshabilitado={cargando}
        >
          <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
            Rol
            <select
              value={borrRol}
              onChange={(e) => setBorrRol(e.target.value)}
              className="min-w-[160px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none"
            >
              {OPCIONES_ROL.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
            Estado
            <select
              value={borrEstado}
              onChange={(e) => setBorrEstado(e.target.value)}
              className="min-w-[140px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none"
            >
              {OPCIONES_ESTADO.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
            Buscar
            <input
              type="text"
              value={borrQ}
              placeholder="Nombre, email o legajo…"
              onChange={(e) => setBorrQ(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') aplicarFiltros();
              }}
              className="min-w-[220px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none"
            />
          </label>
        </FiltrosPanel>

        <UsuarioTable
          usuarios={usuarios}
          fotos={fotos}
          cargando={cargando}
          total={total}
          esPropioUsuario={esPropioUsuario}
          onVerDetalle={(u) => navigate(`/admin/usuarios/${u.id}`)}
          onEditar={abrirEditar}
          onToggleEstado={handleToggleEstado}
          headerRight={<PageSizeSelect value={pageSize} onChange={cambiarPageSize} />}
        />

        <Pagination
          currentPage={paginaActual}
          totalPages={totalPaginas}
          totalElements={total}
          pageSize={pageSize}
          onPageChange={irPagina}
        />
      </div>

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
