// Auditoría — registro de actividad del sistema (C-20).
// Filtros: Módulo (catálogo de GET /admin/audit-catalogo) + Tipo de acción (4 valores fijos).
// Click en una actividad navega al detalle de la entidad (si entidad_id existe)
// o al listado del módulo. Registro inalterable (cadena de hash append-only).
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { StaffShell } from '../ui/shells';
import { ExportButtons } from '../ui/ExportButtons';
import { HelpButton } from '../ui/HelpButton';
import { Icon, Card, LoadingSpinner } from '../ui/components';
import { FiltrosPanel } from '../ui/FiltrosPanel';
import { Pagination } from '../ui/Pagination';
import { RefreshBar } from '../ui/RefreshBar';
import { STAFF_NAV } from '../ui/nav';
import { api } from '../lib/api';
import { useAutoRefresh } from '../lib/useAutoRefresh';
import { useApp } from '../lib/store';
import { configDiff } from './auditoria.helpers';
import type { AuditFiltros, AuditEvento, AuditLogResponse } from '../lib/types';

const SIN_FILTRO: AuditFiltros = {};
const PAGE_SIZE_DEFAULT = 5;

// Fallback ANTES de que responda el backend (evita un select vacío en el primer
// render) — se reemplaza en cuanto llega GET /admin/audit-catalogo. Es la MISMA
// lista que ModuloAuditoria en el backend; si se desincroniza, el catálogo real
// la pisa igual, así que el fallback nunca queda "mintiendo" por mucho tiempo.
const TODOS_MODULOS_FALLBACK = [
  { value: 'USUARIOS',      label: 'Usuarios' },
  { value: 'MATERIAS',      label: 'Materias' },
  { value: 'EXAMENES',      label: 'Exámenes' },
  { value: 'SESIONES',      label: 'Sesiones' },
  { value: 'CONSENTIMIENTO',label: 'Consentimiento' },
  { value: 'BIOMETRIA',     label: 'Biometría' },
  { value: 'EVIDENCIA',     label: 'Evidencia' },
  { value: 'REVISION',      label: 'Revisión' },
  { value: 'MOODLE',        label: 'Moodle' },
  { value: 'CONFIGURACION', label: 'Configuración' },
];

/**
 * Acciones reales por módulo. Cada opción mapea a uno o varios patrones de la
 * columna `accion` (dot-notation, ya poblada en el 100% de las filas). El filtro
 * los envía separados por coma y el backend los combina con OR.
 *
 * Criterio (sin redundancia): se usan los verbos GENÉRICOS (Crear/Editar/Eliminar/
 * Cambio de estado) como base y SOLO se agrega una acción específica donde un
 * genérico no la puede expresar (ej.: sincronizar a Moodle no es CRUD). No se
 * inventan acciones que el sistema no registra.
 *
 * MANTENIMIENTO: a diferencia de los MÓDULOS (que se traen de GET /admin/audit-catalogo,
 * ver TODOS_MODULOS_FALLBACK arriba), esto NO se deriva automáticamente del backend —
 * es una curación manual (agrupa y traduce AccionAuditoria de backend/app/application/audit/acciones.py).
 * Si se agrega una AccionAuditoria nueva y se quiere que aparezca como opción de
 * filtro, hay que agregarla acá a mano.
 */
interface OpcionAccion { label: string; accion: string }

const ACCIONES_POR_MODULO: Record<string, OpcionAccion[]> = {
  USUARIOS: [
    { label: 'Crear',           accion: 'user.create' },
    { label: 'Editar',          accion: 'user.update' },   // incluye cambio de contraseña
    // Baja de usuario = baja LÓGICA (soft-delete). Ella y la reactivación son ambas
    // "cambio de estado". No hay "Eliminar" (borrado físico) para usuarios.
    { label: 'Cambio de estado', accion: 'user.delete,user.reactivate' },
  ],
  MATERIAS: [
    { label: 'Crear',           accion: 'materia.create,comision.create,inscripcion.create' },
    { label: 'Editar',          accion: 'materia.update,comision.update' },
    { label: 'Eliminar',        accion: 'materia.delete,comision.delete,inscripcion.delete' },
    { label: 'Cambio de estado', accion: 'materia.set_activa,comision.set_activa' },
    { label: 'Asignar tutor',  accion: 'comision.set_docente' },
    // c-79: quién coordina la materia decide sobre qué puede operar. El backend
    // ya lo emitía; acá no existía ni como filtro ni como etiqueta (F-07).
    { label: 'Asignar coordinador', accion: 'materia.set_coordinador' },
    { label: 'Asignar profesor', accion: 'materia.set_profesor' },
  ],
  EXAMENES: [
    { label: 'Importar examen', accion: 'examen.import' },
    { label: 'Editar',          accion: 'examen.moodle_target,examen.config_update,examen.seleccion_preguntas' },
    // c-78: la baja de examen es LÓGICA (setea eliminado_en, no borra la fila).
    // Ella y la reactivación son el mismo par que en Usuarios: cambio de estado.
    { label: 'Baja/reactivación de examen', accion: 'examen.baja,examen.reactivar' },
    { label: 'Publicación de notas', accion: 'examen.publicar_notas' },
    { label: 'Duplicación de examen', accion: 'examen.duplicar' },
    {
      label: 'Comisiones del examen',
      accion: 'examen.comision_agregada,examen.comision_quitada',
    },
    {
      // `examen.volver_a_borrador` es el reverso exacto de `examen.habilitar`:
      // va en la misma opción, no en una propia.
      label: 'Habilitación y pool del examen',
      accion:
        'examen.habilitar,examen.volver_a_borrador,examen.pool_actualizado,examen.sorteo_rearmado',
    },
    // El banco vive bajo el módulo EXAMENES (así lo registra el backend). Sin
    // estas dos opciones, sacar una pregunta o una categoría de circulación
    // quedaba auditado pero imposible de buscar.
    {
      label: 'Baja/reactivación de pregunta del banco',
      accion: 'pregunta_banco.baja,pregunta_banco.reactivar',
    },
    {
      label: 'Baja/reactivación de categoría del banco',
      accion: 'categoria_banco.baja,categoria_banco.reactivar',
    },
    {
      // Renombrar o re-anidar. Se audita porque el examen guarda el ID de la
      // categoría, no su nombre: sin esta entrada no queda cómo se llamaba
      // cuando se armó un examen que ya se rindió.
      label: 'Edición de categoría del banco',
      accion: 'categoria_banco.edicion',
    },
  ],
  MOODLE: [
    { label: 'Sincronizar nota', accion: 'moodle.sync' },
    { label: 'Marcar nota como cargada a mano', accion: 'moodle.nota_marcada_manual' },
    { label: 'Conectar cuenta del campus', accion: 'moodle_credencial.conectar' },
    { label: 'Renovar cuenta del campus', accion: 'moodle_credencial.renovar' },
    { label: 'Desconectar cuenta del campus', accion: 'moodle_credencial.desconectar' },
    { label: 'Intentos fallidos repetidos', accion: 'moodle_credencial.intentos_fallidos' },
  ],
  CONSENTIMIENTO: [
    { label: 'Otorgó consentimiento', accion: 'consent.otorgado' },
    { label: 'Eligió vía alternativa', accion: 'consent_alternative_chosen' },
  ],
  BIOMETRIA: [
    { label: 'Verificó identidad',       accion: 'biometria.verificacion' },
    { label: 'Registró foto de referencia', accion: 'enrollment.embedding_referencia.alta' },
    { label: 'Renovó foto de referencia', accion: 'enrollment.embedding_referencia.renovacion' },
  ],
  EVIDENCIA: [
    { label: 'Consultó evidencia', accion: 'acceso_evidencia' },
    { label: 'Guardó evidencia',   accion: 'deposito_evidencia' },
    { label: 'Detectó anomalía',   accion: 'manipulacion_detectada' },
    { label: 'Verificó integridad', accion: 'firma_maestra,verify_chain.' },
    { label: 'Retención / borrado', accion: 'retention.' },
    { label: 'Derecho del titular', accion: 'dsr.,derecho_acceso.' },
  ],
  REVISION: [
    { label: 'Decisión de revisión', accion: 'review.decision.' },
  ],
  CONFIGURACION: [
    // Sin `config.`: no existe ninguna acción con ese prefijo, así que era un
    // patrón muerto que solo podía sumar cero resultados.
    { label: 'Editar', accion: 'config_update' },
  ],
  SESIONES: [
    { label: 'Eliminar sesión de diagnóstico', accion: 'sesion.test.delete' },
    { label: 'Archivar/desarchivar resultado', accion: 'sesion.resultado.archivar' },
  ],
};

/** Etiqueta + color + ícono por acción dot-notation (detalle). */
const ACCION_META: Array<{ match: (a: string) => boolean; label: string; color: string; icon: string }> = [
  { match: (a) => a === 'materia.create', label: 'Creó materia', color: '#10b981', icon: 'school' },
  { match: (a) => a === 'materia.update', label: 'Editó materia', color: '#8b5cf6', icon: 'edit' },
  { match: (a) => a === 'materia.delete', label: 'Eliminó materia', color: '#ef4444', icon: 'delete' },
  { match: (a) => a === 'materia.set_activa', label: 'Cambió estado de materia', color: '#f59e0b', icon: 'toggle_on' },
  { match: (a) => a === 'comision.create', label: 'Creó comisión', color: '#06b6d4', icon: 'groups' },
  { match: (a) => a === 'comision.update', label: 'Editó comisión', color: '#8b5cf6', icon: 'edit' },
  { match: (a) => a === 'comision.delete', label: 'Eliminó comisión', color: '#ef4444', icon: 'delete' },
  { match: (a) => a === 'comision.set_activa', label: 'Cambió el estado de la comisión', color: '#f59e0b', icon: 'toggle_on' },
  { match: (a) => a === 'comision.set_docente', label: 'Asignó docente a la comisión', color: '#06b6d4', icon: 'assignment_ind' },
  { match: (a) => a === 'materia.set_coordinador', label: 'Asignó coordinador a la materia', color: '#06b6d4', icon: 'supervisor_account' },
  { match: (a) => a === 'materia.set_profesor', label: 'Asignó profesor a la materia', color: '#06b6d4', icon: 'co_present' },
  { match: (a) => a === 'inscripcion.create', label: 'Inscribió alumno', color: '#10b981', icon: 'person_add' },
  { match: (a) => a === 'inscripcion.delete', label: 'Dio de baja inscripción', color: '#ef4444', icon: 'person_remove' },
  { match: (a) => a === 'examen.moodle_target', label: 'Fijó destino Moodle', color: '#0891b2', icon: 'link' },
  { match: (a) => a === 'examen.config_update', label: 'Cambió config del examen', color: '#f59e0b', icon: 'tune' },
  { match: (a) => a === 'examen.seleccion_preguntas', label: 'Cambió preguntas', color: '#2563eb', icon: 'quiz' },
  { match: (a) => a === 'examen.baja', label: 'Dio de baja el examen', color: '#ef4444', icon: 'delete' },
  { match: (a) => a === 'examen.reactivar', label: 'Reactivó el examen', color: '#10b981', icon: 'restore_from_trash' },
  { match: (a) => a === 'examen.publicar_notas', label: 'Publicó las notas', color: '#0891b2', icon: 'campaign' },
  { match: (a) => a === 'examen.duplicar', label: 'Duplicó el examen', color: '#7c3aed', icon: 'content_copy' },
  { match: (a) => a === 'examen.comision_agregada', label: 'Sumó una comisión al examen', color: '#10b981', icon: 'group_add' },
  { match: (a) => a === 'examen.comision_quitada', label: 'Quitó una comisión del examen', color: '#ef4444', icon: 'group_remove' },
  { match: (a) => a === 'examen.habilitar', label: 'Habilitó el examen', color: '#10b981', icon: 'visibility' },
  { match: (a) => a === 'examen.pool_actualizado', label: 'Amplió las preguntas del sorteo', color: '#0891b2', icon: 'library_add' },
  // Rearmar no es ampliar: acá se pudo SACAR una categoría del examen.
  { match: (a) => a === 'examen.sorteo_rearmado', label: 'Cambió las preguntas del sorteo', color: '#0891b2', icon: 'shuffle' },
  { match: (a) => a === 'moodle.sync', label: 'Sincronizó a Moodle', color: '#7c3aed', icon: 'sync' },
  { match: (a) => a === 'moodle_credencial.conectar', label: 'Conectó su cuenta del campus', color: '#2563eb', icon: 'link' },
  { match: (a) => a === 'moodle_credencial.renovar', label: 'Renovó su cuenta del campus', color: '#2563eb', icon: 'autorenew' },
  { match: (a) => a === 'moodle_credencial.desconectar', label: 'Desconectó su cuenta del campus', color: '#f59e0b', icon: 'link_off' },
  { match: (a) => a === 'moodle_credencial.intentos_fallidos', label: 'Intentos fallidos repetidos', color: '#ef4444', icon: 'gpp_maybe' },
  { match: (a) => a.startsWith('examen.'), label: 'Cargó examen', color: '#2563eb', icon: 'fact_check' },
  { match: (a) => a === 'enrollment.embedding_referencia.alta', label: 'Registró foto de referencia', color: '#8b5cf6', icon: 'photo_camera' },
  { match: (a) => a.startsWith('enrollment'), label: 'Renovó foto de referencia', color: '#8b5cf6', icon: 'photo_camera' },
  { match: (a) => a.startsWith('biometria'), label: 'Verificó identidad', color: '#8b5cf6', icon: 'face' },
  { match: (a) => a.startsWith('consent'), label: 'Consentimiento', color: '#0d9488', icon: 'fact_check' },
  { match: (a) => a === 'user.create', label: 'Alta de usuario', color: '#059669', icon: 'person_add' },
  { match: (a) => a === 'user.update', label: 'Editó usuario', color: '#8b5cf6', icon: 'manage_accounts' },
  { match: (a) => a === 'user.delete', label: 'Cambió estado de usuario', color: '#f59e0b', icon: 'toggle_off' },
  { match: (a) => a === 'user.reactivate', label: 'Cambió estado de usuario', color: '#10b981', icon: 'toggle_on' },
  { match: (a) => a.startsWith('config'), label: 'Cambió configuración', color: '#f59e0b', icon: 'settings' },
  { match: (a) => a.startsWith('review.decision'), label: 'Decisión de revisión', color: '#d97706', icon: 'gavel' },
  { match: (a) => a === 'acceso_evidencia', label: 'Consultó evidencia', color: '#0ea5e9', icon: 'folder_open' },
  { match: (a) => a === 'deposito_evidencia', label: 'Guardó evidencia', color: '#2563eb', icon: 'inventory_2' },
  { match: (a) => a === 'manipulacion_detectada', label: 'Detectó anomalía', color: '#ef4444', icon: 'gpp_maybe' },
  { match: (a) => a.startsWith('firma_maestra') || a.startsWith('verify_chain'), label: 'Verificó integridad', color: '#7c3aed', icon: 'verified_user' },
  { match: (a) => a.startsWith('retention'), label: 'Retención / borrado', color: '#64748b', icon: 'auto_delete' },
  { match: (a) => a.startsWith('dsr') || a.startsWith('derecho_acceso'), label: 'Derecho del titular', color: '#0d9488', icon: 'policy' },
  { match: (a) => a === 'sesion.test.delete', label: 'Eliminó sesión de diagnóstico', color: '#ef4444', icon: 'delete' },
  { match: (a) => a === 'sesion.resultado.archivar', label: 'Archivó/desarchivó resultado', color: '#f59e0b', icon: 'archive' },
];

function accionMeta(accion: string): { label: string; color: string; icon: string } {
  return ACCION_META.find((m) => m.match(accion)) ?? { label: accion, color: '#64748b', icon: 'bolt' };
}


/** Ruta al MÓDULO general (listado) según `modulo` — usada cuando la entidad
 * afectada no tiene página propia, o cuando no hay entidad_id para linkear. */
function rutaDeModulo(modulo: string | null | undefined): string | null {
  switch (modulo) {
    case 'USUARIOS': return '/admin/usuarios';
    case 'MATERIAS': return '/admin/materias';
    case 'EXAMENES': return '/admin/examenes';
    case 'SESIONES':
    case 'BIOMETRIA':
    case 'CONSENTIMIENTO':
    case 'EVIDENCIA': return '/admin/proctoring-sessions';
    case 'REVISION': return '/admin/cola-revision';
    case 'MOODLE': return '/admin/examenes';
    case 'CONFIGURACION': return '/admin/configuracion';
    default: return null;
  }
}

/** Fallback: deriva el módulo del patrón de `accion` (entradas sin `modulo`). */
function rutaDeAccion(accion: string): string | null {
  const a = accion ?? '';
  if (a.startsWith('config')) return '/admin/configuracion';
  if (a.startsWith('user.')) return '/admin/usuarios';
  if (a.startsWith('materia.') || a.startsWith('comision.') || a.startsWith('inscripcion.')) return '/admin/materias';
  if (a.startsWith('examen.') || a === 'moodle.sync') return '/admin/examenes';
  if (a.startsWith('review.') || a.startsWith('enrollment') || a.startsWith('biometria') || a.startsWith('consent')) return '/admin/proctoring-sessions';
  return null;
}

/** Entidades que tienen PÁGINA PROPIA de detalle (con su propio id en la URL).
 * El resto (MATERIA/COMISION/INSCRIPCION/CONSENTIMIENTO/...) no tiene pantalla
 * propia — su "detalle" es simplemente el listado del módulo. */
const ENTIDADES_CON_PAGINA_PROPIA = new Set(['USUARIO', 'EXAMEN', 'SESION']);

/** true si esta actividad tiene una página de DETALLE propia a la que ir
 * (no solo la página general del módulo). Determina la etiqueta del botón. */
function tieneDetallePropio(evento: AuditEvento): boolean {
  return Boolean(evento.entidad_id) && ENTIDADES_CON_PAGINA_PROPIA.has(evento.entidad ?? '');
}

/** Ruta de navegación de una actividad: al detalle propio de la entidad si lo
 * tiene, o si no a la página general del módulo (o la heurística por acción
 * para entradas viejas sin `modulo`). */
function navegarA(evento: AuditEvento): string | null {
  if (tieneDetallePropio(evento)) {
    switch (evento.entidad) {
      case 'USUARIO': return `/admin/usuarios/${evento.entidad_id}`;
      case 'EXAMEN': return `/admin/examenes/${evento.entidad_id}/resultados`;
      case 'SESION': return '/admin/proctoring-session-detail';  // handleClickActividad sets store
    }
  }
  return rutaDeModulo(evento.modulo) ?? rutaDeAccion(evento.accion ?? '');
}

function fmtFecha(iso: string): string {
  const d = new Date(iso.replace(' ', 'T'));
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'medium' });
}

function Proposito({ proposito }: { proposito: string }) {
  const cambios = configDiff(proposito);
  if (cambios === null) {
    return <p className="mt-1.5 text-[13.5px] text-on-surface" title={proposito}>{proposito}</p>;
  }
  if (cambios.length === 0) {
    return <p className="mt-1.5 text-[13.5px] text-on-surface-variant">Guardó la configuración sin cambios.</p>;
  }
  return (
    <details className="mt-1.5 group">
      <summary className="flex cursor-pointer list-none items-center gap-1.5 text-[13.5px] text-on-surface">
        <Icon name="expand_more" className="text-[18px] text-on-surface-variant transition-transform group-open:rotate-180" />
        Cambió <strong className="font-semibold">{cambios.length}</strong>{' '}
        {cambios.length === 1 ? 'parámetro' : 'parámetros'}
      </summary>
      <ul className="mt-2 space-y-1.5 border-l-2 border-surface-200 pl-3">
        {cambios.map((c) => (
          <li key={c.key} className="text-[12.5px] text-on-surface-variant">
            <span className="font-medium text-on-surface">{c.label}</span>:{' '}
            <span className="line-through">{c.antes}</span>
            <Icon name="arrow_forward" className="mx-1 align-middle text-[13px]" />
            <span className="font-semibold text-on-surface">{c.despues}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}

export default function Auditoria() {
  const navigate = useNavigate();
  const [data, setData] = useState<AuditLogResponse | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [borrador, setBorrador] = useState<AuditFiltros>(SIN_FILTRO);
  const [filtros, setFiltros] = useState<AuditFiltros>(SIN_FILTRO);
  const [offset, setOffset] = useState(0);
  const [pageSize, setPageSize] = useState(PAGE_SIZE_DEFAULT);
  const [exportando, setExportando] = useState<'xlsx' | 'pdf' | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | undefined>();
  const [modulos, setModulos] = useState(TODOS_MODULOS_FALLBACK);

  useEffect(() => {
    api.obtenerAuditCatalogo()
      .then((catalogo) => { if (catalogo.length > 0) setModulos(catalogo); })
      .catch(() => {}); // fallback ya está seteado; no hay nada más que mostrar
  }, []);

  const moduleLabel = useMemo(
    () => Object.fromEntries(modulos.map((m) => [m.value, m.label])) as Record<string, string>,
    [modulos],
  );

  /** Descarga el registro con los filtros APLICADOS y dispara el guardado. */
  const exportar = async (formato: 'xlsx' | 'pdf') => {
    setExportando(formato);
    try {
      const blob = await api.exportarAuditoria(formato, filtros);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `auditoria.${formato}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      // Liberar el object URL: sin esto el blob queda retenido en memoria
      // mientras viva la pestaña, y estos archivos no son chicos.
      URL.revokeObjectURL(url);
    } catch {
      setError('No se pudo generar el archivo. Reintentá en un momento.');
    } finally {
      setExportando(null);
    }
  };

  const cargar = useCallback((f: AuditFiltros, off: number, size: number) => {
    setCargando(true);
    setError(null);
    api
      .obtenerAuditLog(f, size, off)
      .then((r) => { setData(r); setError(null); setLastUpdatedAt(Date.now()); })
      .catch((e: unknown) => {
        const status = (e as { status?: number })?.status;
        setData(null);
        setError(
          status === 403
            ? 'No tenés permisos para ver la auditoría.'
            : 'No se pudo cargar el registro de auditoría. Intentá de nuevo.',
        );
      })
      .finally(() => setCargando(false));
  }, []);

  useEffect(() => { cargar(filtros, offset, pageSize); }, [cargar, filtros, offset, pageSize]);

  // Auto-refresh cada 5 min (el registro es append-only: refrescar trae lo nuevo).
  useAutoRefresh(() => cargar(filtros, offset, pageSize), undefined, !cargando);

  const cambiarPageSize = (size: number) => { setOffset(0); setPageSize(size); };
  const setCampo = (parche: Partial<AuditFiltros>) => setBorrador((p) => ({ ...p, ...parche }));
  const aplicar = () => { setOffset(0); setFiltros(borrador); };
  const limpiar = () => { setBorrador(SIN_FILTRO); setOffset(0); setFiltros(SIN_FILTRO); };

  const hayFiltros = Boolean(borrador.actor || borrador.modulo || borrador.accion || borrador.desde || borrador.hasta);
  const hayCambios =
    (borrador.actor ?? '') !== (filtros.actor ?? '') ||
    (borrador.modulo ?? '') !== (filtros.modulo ?? '') ||
    (borrador.accion ?? '') !== (filtros.accion ?? '') ||
    (borrador.desde ?? '') !== (filtros.desde ?? '') ||
    (borrador.hasta ?? '') !== (filtros.hasta ?? '');

  const total = data?.total ?? 0;
  const totalPaginas = Math.max(1, Math.ceil(total / pageSize));
  const paginaActual = Math.floor(offset / pageSize) + 1;
  const irAPagina = (n: number) => setOffset((Math.max(1, Math.min(n, totalPaginas)) - 1) * pageSize);

  const setProctoringSessionId = useApp((s) => s.setProctoringSessionId);
  const setProctoringDetailBackRoute = useApp((s) => s.setProctoringDetailBackRoute);

  const handleClickActividad = (e: AuditEvento) => {
    if (e.entidad === 'SESION' && e.entidad_id && tieneDetallePropio(e)) {
      setProctoringSessionId(e.entidad_id);
      setProctoringDetailBackRoute('/admin/auditoria');
      navigate('/admin/proctoring-session-detail/' + e.entidad_id);
      return;
    }
    const ruta = navegarA(e);
    if (ruta) navigate(ruta);
  };

  return (
    <StaffShell
      nav={STAFF_NAV}
      title="Auditoría"
      subtitle="Registro de actividad de la plataforma: quién hizo qué y cuándo. El registro no se puede alterar."
      help={
        <HelpButton title="Auditoría">
          <p>
            Todo lo importante que pasa en la plataforma queda asentado acá:
            altas y bajas de usuarios, cambios de configuración, decisiones de
            revisión y descargas de reportes.
          </p>
          <p>
            El registro es <strong>inalterable</strong>: cada entrada se encadena
            con la anterior mediante una firma. Si alguien intentara modificar o
            borrar algo, la cadena se rompe y el sistema lo detecta.
          </p>
        </HelpButton>
      }
    >
      <RefreshBar
        texto="Auditoría"
        lastUpdatedAt={lastUpdatedAt}
        cargando={cargando}
        onActualizar={() => cargar(filtros, offset, pageSize)}
      />

      {/* Export del registro. Descarga lo MISMO que se está viendo: usa `filtros`
          (los aplicados), no `borrador` — si tomara el borrador, el archivo saldría
          con un recorte que la persona todavía no confirmó en pantalla. */}
      <div className="mb-md flex justify-end gap-2">
        {/* Mismo componente que Estadísticas y que el padrón de cada comisión: el
            markup estaba copiado y la tercera copia ya había derivado a otro estilo. */}
        <ExportButtons
          exportando={exportando === 'xlsx' ? 'excel' : exportando}
          disabled={cargando}
          onExportar={(f) => exportar(f === 'excel' ? 'xlsx' : 'pdf')}
        />
      </div>

      <div className="mb-lg">
        <FiltrosPanel onAplicar={aplicar} onLimpiar={limpiar} hayFiltros={hayFiltros} hayCambios={hayCambios} aplicarDeshabilitado={cargando}>
          <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
            Actor
            <input
              type="text"
              value={borrador.actor ?? ''}
              placeholder="Email o legajo institucional"
              onChange={(e) => setCampo({ actor: e.target.value || undefined })}
              className="min-w-[180px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-surface-500 focus:outline-none"
            />
          </label>
          <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
            Módulo
            <select
              value={borrador.modulo ?? ''}
              onChange={(e) => {
                const mod = e.target.value || undefined;
                // Al cambiar de módulo, la acción elegida deja de aplicar → se resetea.
                setCampo({ modulo: mod, accion: undefined });
              }}
              className="min-w-[180px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-surface-500 focus:outline-none"
            >
              <option value="">Todos los módulos</option>
              {modulos.map((m) => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
            Acción
            <select
              value={borrador.accion ?? ''}
              onChange={(e) => setCampo({ accion: e.target.value || undefined })}
              disabled={!borrador.modulo || (ACCIONES_POR_MODULO[borrador.modulo]?.length ?? 0) === 0}
              className="min-w-[180px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-surface-500 focus:outline-none disabled:opacity-50"
            >
              <option value="">Todas las acciones</option>
              {(borrador.modulo ? ACCIONES_POR_MODULO[borrador.modulo] ?? [] : []).map((a) => (
                <option key={a.accion} value={a.accion}>{a.label}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
            Desde
            <input
              type="date"
              value={borrador.desde?.slice(0, 10) ?? ''}
              onChange={(e) => setCampo({ desde: e.target.value ? `${e.target.value}T00:00:00` : undefined })}
              className="rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-surface-500 focus:outline-none"
            />
          </label>
          <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
            Hasta
            <input
              type="date"
              value={borrador.hasta?.slice(0, 10) ?? ''}
              onChange={(e) => setCampo({ hasta: e.target.value ? `${e.target.value}T23:59:59` : undefined })}
              className="rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-surface-500 focus:outline-none"
            />
          </label>
        </FiltrosPanel>
      </div>

      {error ? (
        <div className="flex flex-col items-center text-center gap-md py-2xl text-on-surface-variant">
          <Icon name="error" className="text-[40px] text-error" fill />
          <p className="text-[15px] max-w-sm">{error}</p>
          <button
            type="button"
            onClick={() => cargar(filtros, offset, pageSize)}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-md border border-surface-200 bg-white text-[14px] font-medium hover:bg-primary-50"
          >
            <Icon name="refresh" className="text-[16px]" /> Reintentar
          </button>
        </div>
      ) : cargando || !data ? (
        <div className="py-2xl flex items-center justify-center">
          <LoadingSpinner size="md" label="Cargando auditoría…" />
        </div>
      ) : (
        <>
          {/* Banner de cadena alterada: prominente, encima de todo */}
          {!data.cadena_valida && (
            <div className="mb-4 flex items-start gap-3 rounded-xl border border-error-300 bg-error-50 px-5 py-4">
              <Icon name="gpp_bad" className="mt-0.5 shrink-0 text-[22px] text-error-600" fill />
              <div>
                <p className="text-[14px] font-semibold text-error-700">Cadena de custodia alterada</p>
                <p className="mt-0.5 text-[12.5px] text-error-600">
                  El registro puede haber sido modificado externamente. Revisá los hashes con el administrador del sistema.
                </p>
              </div>
            </div>
          )}

          {/* Barra de estado: conteo + verificación cuando todo está bien */}
          <div className="mb-3 flex items-center justify-between text-[12.5px] text-on-surface-variant">
            <span>
              <strong className="text-on-surface tabular-nums">{data.total}</strong>{' '}
              {data.total === 1 ? 'actividad' : 'actividades'}
            </span>
            {data.cadena_valida && (
              <span className="inline-flex items-center gap-1 text-success-700">
                <Icon name="verified_user" className="text-[14px]" fill />
                Registro verificado
              </span>
            )}
          </div>

          {data.items.length === 0 ? (
            <Card>
              <div className="py-xl flex flex-col items-center text-center gap-md text-on-surface-variant">
                <Icon name="history" className="text-[36px]" />
                <p className="text-[14px]">No hay actividad registrada para estos filtros.</p>
              </div>
            </Card>
          ) : (
            <div className="flex flex-col gap-2">
              {data.items.map((e) => {
                const meta = accionMeta(e.accion);
                const nombre = e.actor_nombre ?? e.actor;
                const subtexto = e.actor_nombre ? (e.actor_email ?? e.actor) : null;
                const ruta = navegarA(e);
                return (
                  <div
                    key={e.id}
                    onClick={() => handleClickActividad(e)}
                    className={`flex items-start gap-4 rounded-xl border border-surface-200 bg-white px-5 py-4 shadow-xs transition-all duration-200 ${ruta ? 'cursor-pointer hover:shadow-sm hover:border-surface-300' : ''}`}
                  >
                    <span
                      className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl"
                      style={{ backgroundColor: `${meta.color}15`, color: meta.color }}
                      aria-hidden
                    >
                      <Icon name={meta.icon} className="text-[20px]" fill />
                    </span>

                    <div className="min-w-0 flex-1">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span
                            className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold"
                            style={{ backgroundColor: `${meta.color}15`, color: meta.color }}
                          >
                            {meta.label}
                          </span>
                          {e.modulo && (
                            <span className="inline-flex items-center rounded-full bg-surface-100 px-2.5 py-0.5 text-xs font-medium text-surface-600">
                              {moduleLabel[e.modulo] ?? (e.modulo.charAt(0) + e.modulo.slice(1).toLowerCase())}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          {ruta && (
                            <span className="inline-flex items-center gap-1 text-xs font-medium text-primary">
                              <span>{tieneDetallePropio(e) ? 'Ver detalle' : 'Ver módulo'}</span>
                              <Icon name="open_in_new" className="text-[13px]" />
                            </span>
                          )}
                          <span className="text-xs text-surface-400 tabular-nums whitespace-nowrap">
                            {fmtFecha(e.timestamp)}
                          </span>
                        </div>
                      </div>

                      <div className="mt-2 flex items-center gap-2">
                        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-surface-100 text-surface-500">
                          <Icon name="person" className="text-[14px]" fill />
                        </span>
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-surface-800 truncate" title={nombre}>
                            {nombre}
                          </p>
                          {subtexto && (
                            <p className="text-xs text-surface-400 truncate" title={subtexto}>
                              {subtexto}
                            </p>
                          )}
                        </div>
                      </div>
                      {e.proposito && <Proposito proposito={e.proposito} />}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <div className="mt-lg">
            <Pagination
              currentPage={paginaActual}
              totalPages={totalPaginas}
              totalElements={total}
              pageSize={pageSize}
              onPageChange={irAPagina}
              onPageSizeChange={cambiarPageSize}
            />
          </div>
        </>
      )}
    </StaffShell>
  );
}
