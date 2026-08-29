/**
 * GestionUsuarios — listado administrativo de usuarios (C-61).
 *
 * Ruta: /admin/usuarios (roles: admin_sistema)
 * Accede a api.listarUsuarios / api.eliminarUsuario / api.reactivarUsuario.
 * Alta y edición viven en páginas propias (/admin/usuarios/nuevo y
 * /admin/usuarios/:id/editar), no inline en este listado.
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
import { etiquetaConBaja } from './materias/filtroEstado';
import { api } from '../lib/api';
import type { UsuarioAdmin, Materia, Comision } from '../lib/types';
import { OPCIONES_ROL, OPCIONES_ESTADO } from './admin/components/UsuarioHelpers';
import { UsuarioTable } from './admin/components/UsuarioTable';
import { FiltrosPanel } from '../ui/FiltrosPanel';
import { ESTADO_INICIAL, paramsDeEstado } from './GestionUsuarios.filtros';
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
  const [filtroEstado, setFiltroEstado] = useState<string>(ESTADO_INICIAL);
  const [filtroQ, setFiltroQ] = useState('');
  const [borrRol, setBorrRol] = useState('');
  const [borrEstado, setBorrEstado] = useState<string>(ESTADO_INICIAL);
  const [borrQ, setBorrQ] = useState('');

  // Filtro de materia/comisión: solo aplica (y solo se muestra) cuando el rol
  // filtrado es "estudiante" — los demás roles nunca tienen inscripción.
  const [materias, setMaterias] = useState<Materia[]>([]);
  const [comisiones, setComisiones] = useState<Comision[]>([]);
  const [borrMateria, setBorrMateria] = useState('');
  const [borrComision, setBorrComision] = useState('');
  const [filtroMateria, setFiltroMateria] = useState('');
  const [filtroComision, setFiltroComision] = useState('');

  useEffect(() => {
    if (borrRol !== 'estudiante') {
      setBorrMateria('');
      setBorrComision('');
      return;
    }
    api.materiasDisponibles().then(setMaterias).catch(() => {});
  }, [borrRol]);

  useEffect(() => {
    if (!borrMateria) { setComisiones([]); setBorrComision(''); return; }
    api.comisionesDeMateria(borrMateria).then(setComisiones).catch(() => setComisiones([]));
    setBorrComision('');
  }, [borrMateria]);

  const [fotos, setFotos] = useState<Record<string, string>>({});
  // Ids a los que YA se les pidió la foto, con o sin resultado.
  //
  // `cargarUsuarios` es un useCallback con deps vacías, así que leía el `fotos`
  // del primer render (siempre `{}`) y volvía a pedir TODAS las fotos en cada
  // carga, paginado y auto-refresh. Para un usuario sin foto el endpoint
  // responde 404, así que cada recarga repetía un 404 por usuario y llenaba la
  // consola de errores. Un ref no queda atrapado en la clausura y recuerda
  // también los "no tiene", que es lo que evita repetir el 404.
  const fotosPedidas = useRef<Set<string>>(new Set());

  const [aBajar, setABajar] = useState<UsuarioAdmin | null>(null);

  const cargarUsuarios = useCallback(async (
    o: number, rol: string, estado: string, q: string, materiaId: string, comisionId: string,
  ) => {
    setCargando(true);
    try {
      const data = await api.listarUsuarios(pageSizeRef.current, o, {
        rol: rol || undefined,
        // SIEMPRE explícito: omitirlo hace que el backend aplique su propio
        // default ('activo') y la tabla contradiga al desplegable.
        estado: paramsDeEstado(estado),
        q: q || undefined,
        materia_id: rol === 'estudiante' ? (materiaId || undefined) : undefined,
        comision_id: rol === 'estudiante' ? (comisionId || undefined) : undefined,
      });
      setUsuarios(data.items);
      setTotal(data.total);
      setLastUpdatedAt(Date.now());
      for (const u of data.items) {
        if (fotosPedidas.current.has(u.id)) continue;
        fotosPedidas.current.add(u.id);
        api.obtenerFotoPerfilDeUsuario(u.id).then((foto) => {
          if (foto) setFotos((prev) => ({ ...prev, [u.id]: foto }));
        });
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

  useEffect(() => { cargarUsuarios(0, filtroRol, filtroEstado, filtroQ, filtroMateria, filtroComision); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-refresh cada 5 min conservando página y filtros actuales.
  useAutoRefresh(() => cargarUsuarios(offset, filtroRol, filtroEstado, filtroQ, filtroMateria, filtroComision), undefined, !cargando);

  const hayCambiosFiltros =
    borrRol !== filtroRol || borrEstado !== filtroEstado || borrQ.trim() !== filtroQ
    || borrMateria !== filtroMateria || borrComision !== filtroComision;
  const hayFiltrosActivos = Boolean(borrRol) || borrEstado !== ESTADO_INICIAL || Boolean(borrQ)
    || Boolean(borrMateria) || Boolean(borrComision);

  function aplicarFiltros() {
    const q = borrQ.trim();
    setFiltroRol(borrRol);
    setFiltroEstado(borrEstado);
    setFiltroQ(q);
    setFiltroMateria(borrMateria);
    setFiltroComision(borrComision);
    setOffset(0);
    cargarUsuarios(0, borrRol, borrEstado, q, borrMateria, borrComision);
  }

  function limpiarFiltros() {
    setBorrRol('');
    setBorrEstado(ESTADO_INICIAL);
    setBorrQ('');
    setBorrMateria('');
    setBorrComision('');
    setFiltroRol('');
    setFiltroEstado(ESTADO_INICIAL);
    setFiltroQ('');
    setFiltroMateria('');
    setFiltroComision('');
    setOffset(0);
    cargarUsuarios(0, '', ESTADO_INICIAL, '', '', '');
  }

  async function handleBaja() {
    if (!aBajar) return;
    const u = aBajar;
    setABajar(null);
    try {
      await api.eliminarUsuario(u.id);
      toast.success(`${u.email} dado de baja.`);
      await cargarUsuarios(offset, filtroRol, filtroEstado, filtroQ, filtroMateria, filtroComision);
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
        await cargarUsuarios(offset, filtroRol, filtroEstado, filtroQ, filtroMateria, filtroComision);
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
    cargarUsuarios(nuevoOffset, filtroRol, filtroEstado, filtroQ, filtroMateria, filtroComision);
  }

  function cambiarPageSize(size: number) {
    pageSizeRef.current = size;
    setPageSize(size);
    setOffset(0);
    cargarUsuarios(0, filtroRol, filtroEstado, filtroQ, filtroMateria, filtroComision);
  }

  function esPropioUsuario(u: UsuarioAdmin): boolean {
    if (!principal) return false;
    return u.email === principal.email || u.username === principal.username;
  }

  return (
    <StaffShell
      nav={STAFF_NAV}
      title="Gestión de usuarios"
      subtitle="Alta, edición y baja lógica de usuarios de la plataforma."
      help={
        <HelpButton title="Gestión de usuarios">
          <p>Acá das de alta, editás y cambiás el estado de los usuarios. Solo visible para administradores del sistema.</p>
          {/* Faltaba Profesor: son CINCO roles asignables (ver ROLES_FORMULARIO
              en lib/constants/roles.ts y el enum Rol del backend). */}
          <p>Los roles disponibles son <em>Estudiante</em>, <em>Tutor</em>, <em>Profesor</em>, <em>Coordinador</em> y <em>Admin</em>. Al elegir uno, el formulario te explica qué puede hacer cada uno.</p>
          <p>La baja es lógica: el usuario no se borra, solo pierde acceso. La evidencia asociada queda intacta.</p>
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
          onActualizar={() => cargarUsuarios(offset, filtroRol, filtroEstado, filtroQ, filtroMateria, filtroComision)}
        />
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
          {borrRol === 'estudiante' && (<>
            <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
              Materia
              <select
                value={borrMateria}
                onChange={(e) => setBorrMateria(e.target.value)}
                className="min-w-[160px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none"
              >
                <option value="">Todas las materias</option>
                {materias.map((m) => (
                  <option key={m.id} value={m.id}>{etiquetaConBaja(m, m.nombre)}</option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
              Comisión
              <select
                value={borrComision}
                onChange={(e) => setBorrComision(e.target.value)}
                disabled={!borrMateria}
                className="min-w-[160px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none disabled:opacity-50"
              >
                <option value="">Todas las comisiones</option>
                {comisiones.map((c) => (
                  <option key={c.id} value={c.id}>{c.nombre}</option>
                ))}
              </select>
            </label>
          </>)}
          <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
            Buscar
            <input
              type="text"
              value={borrQ}
              placeholder="Nombre, email o usuario…"
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
          onEditar={(u) => navigate(`/admin/usuarios/${u.id}/editar`)}
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
