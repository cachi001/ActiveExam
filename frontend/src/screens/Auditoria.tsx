// Página de Auditoría / registro de actividad (C-20). Vista SOLO-LECTURA del
// audit_log inmutable (append-only + cadena de hash): quién hizo qué y cuándo.
//
// Contrato de carga resiliente (C-73): cargando / error / vacío-real / cargado.
// Los filtros se editan en un borrador y se aplican con "Aplicar filtros"
// (panel genérico FiltrosPanel). El badge de cadena avisa si la integridad se
// rompió (tamper-evident). Nada acá muta el registro.
import { useCallback, useEffect, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { HelpButton } from '../ui/HelpButton';
import { Icon, Card, LoadingSpinner } from '../ui/components';
import { FiltrosPanel } from '../ui/FiltrosPanel';
import { Pagination } from '../ui/Pagination';
import { STAFF_NAV } from '../ui/nav';
import { api } from '../lib/api';
import { configDiff } from './auditoria.helpers';
import type { AuditFiltros, AuditLogResponse } from '../lib/types';

const SIN_FILTRO: AuditFiltros = {};
const PAGE_SIZE_DEFAULT = 5;

/** Etiqueta + color + ícono legible de cada acción (los códigos son dot-namespaced). */
const ACCION_META: Array<{ match: (a: string) => boolean; label: string; color: string; icon: string }> = [
  { match: (a) => a === 'materia.create', label: 'Creó materia', color: '#10b981', icon: 'school' },
  { match: (a) => a === 'comision.create', label: 'Creó comisión', color: '#06b6d4', icon: 'groups' },
  { match: (a) => a === 'examen.create' || a.startsWith('examen.import'), label: 'Cargó examen', color: '#2563eb', icon: 'quiz' },
  { match: (a) => a.startsWith('biometria'), label: 'Verificación biométrica', color: '#8b5cf6', icon: 'face' },
  { match: (a) => a.startsWith('consent'), label: 'Aceptó consentimiento', color: '#0d9488', icon: 'fact_check' },
  { match: (a) => a === 'user.create', label: 'Alta de usuario', color: '#059669', icon: 'person_add' },
  { match: (a) => a === 'user.delete', label: 'Baja de usuario', color: '#ef4444', icon: 'person_remove' },
  { match: (a) => a === 'user.update', label: 'Editó usuario', color: '#8b5cf6', icon: 'manage_accounts' },
  { match: (a) => a === 'config_update' || a.startsWith('config'), label: 'Cambió configuración', color: '#f59e0b', icon: 'settings' },
  { match: (a) => a.startsWith('review.decision'), label: 'Decisión de revisión', color: '#d97706', icon: 'gavel' },
];
function accionMeta(accion: string): { label: string; color: string; icon: string } {
  return ACCION_META.find((m) => m.match(accion)) ?? { label: accion, color: '#64748b', icon: 'bolt' };
}

function fmtFecha(iso: string): string {
  const d = new Date(iso.replace(' ', 'T'));
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'medium' });
}

/** Propósito de una entrada: texto plano, salvo las acciones de config, que se
 * resumen como "Cambió N parámetros" con el detalle antes→después colapsable
 * (en vez de volcar el JSON crudo). */
function Proposito({ proposito }: { proposito: string }) {
  const cambios = configDiff(proposito);

  // No es un diff de config → texto tal cual.
  if (cambios === null) {
    return (
      <p className="mt-1.5 text-[13.5px] text-on-surface" title={proposito}>
        {proposito}
      </p>
    );
  }

  // Config sin cambios efectivos (raro): mensaje neutro, sin JSON.
  if (cambios.length === 0) {
    return <p className="mt-1.5 text-[13.5px] text-on-surface-variant">Guardó la configuración sin cambios.</p>;
  }

  return (
    <details className="mt-1.5 group">
      <summary className="flex cursor-pointer list-none items-center gap-1.5 text-[13.5px] text-on-surface">
        <Icon
          name="expand_more"
          className="text-[18px] text-on-surface-variant transition-transform group-open:rotate-180"
        />
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
  const [data, setData] = useState<AuditLogResponse | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [borrador, setBorrador] = useState<AuditFiltros>(SIN_FILTRO);
  const [filtros, setFiltros] = useState<AuditFiltros>(SIN_FILTRO);
  const [offset, setOffset] = useState(0);
  const [pageSize, setPageSize] = useState(PAGE_SIZE_DEFAULT);

  const cargar = useCallback((f: AuditFiltros, off: number, size: number) => {
    setCargando(true);
    setError(null);
    api
      .obtenerAuditLog(f, size, off)
      .then((r) => {
        setData(r);
        setError(null);
      })
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

  useEffect(() => {
    cargar(filtros, offset, pageSize);
  }, [cargar, filtros, offset, pageSize]);

  const cambiarPageSize = (size: number) => {
    setOffset(0);
    setPageSize(size);
  };

  const setCampo = (parche: Partial<AuditFiltros>) => setBorrador((p) => ({ ...p, ...parche }));
  const aplicar = () => {
    setOffset(0);
    setFiltros(borrador);
  };
  const limpiar = () => {
    setBorrador(SIN_FILTRO);
    setOffset(0);
    setFiltros(SIN_FILTRO);
  };
  const hayFiltros = Boolean(borrador.actor || borrador.accion || borrador.desde || borrador.hasta);
  const hayCambios =
    (borrador.actor ?? '') !== (filtros.actor ?? '') ||
    (borrador.accion ?? '') !== (filtros.accion ?? '') ||
    (borrador.desde ?? '') !== (filtros.desde ?? '') ||
    (borrador.hasta ?? '') !== (filtros.hasta ?? '');

  const total = data?.total ?? 0;
  const totalPaginas = Math.max(1, Math.ceil(total / pageSize));
  const paginaActual = Math.floor(offset / pageSize) + 1;
  const irAPagina = (n: number) => setOffset((Math.max(1, Math.min(n, totalPaginas)) - 1) * pageSize);

  return (
    <StaffShell
      nav={STAFF_NAV}
      title="Auditoría"
      subtitle="Registro de actividad de la plataforma: quién hizo qué y cuándo. Inalterable (cadena de custodia)."
      help={
        <HelpButton title="Auditoría">
          <p>
            Todo lo importante que pasa en la plataforma queda asentado acá:
            inicios de sesión, altas y bajas de usuarios, cambios de
            configuración, decisiones de revisión y descargas de reportes.
          </p>
          <p>
            El registro es <strong>inalterable</strong>: cada entrada se encadena
            con la anterior mediante una firma. Si alguien intentara modificar o
            borrar algo, la cadena se rompe y el sistema lo detecta.
          </p>
        </HelpButton>
      }
    >
      {/* Estado de la cadena de custodia */}
      {data && (
        <div className="mb-md flex justify-end">
          {data.cadena_valida ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-success-50 px-3 py-1 text-[12.5px] font-semibold text-success-700 border border-success-200">
              <Icon name="verified_user" className="text-[15px]" fill />
              Cadena de custodia íntegra
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-error-50 px-3 py-1 text-[12.5px] font-semibold text-error-700 border border-error-200">
              <Icon name="gpp_bad" className="text-[15px]" fill />
              Cadena alterada — revisar
            </span>
          )}
        </div>
      )}

      <div className="mb-lg">
        <FiltrosPanel onAplicar={aplicar} onLimpiar={limpiar} hayFiltros={hayFiltros} hayCambios={hayCambios} aplicarDeshabilitado={cargando}>
          <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
            Actor (usuario)
            <input
              type="text"
              value={borrador.actor ?? ''}
              placeholder="email o parte…"
              onChange={(e) => setCampo({ actor: e.target.value || undefined })}
              className="min-w-[180px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none"
            />
          </label>
          <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
            Acción
            <input
              type="text"
              value={borrador.accion ?? ''}
              placeholder="ej: login, export, user…"
              onChange={(e) => setCampo({ accion: e.target.value || undefined })}
              className="min-w-[160px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none"
            />
          </label>
          <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
            Desde
            <input
              type="date"
              value={borrador.desde?.slice(0, 10) ?? ''}
              onChange={(e) => setCampo({ desde: e.target.value ? `${e.target.value}T00:00:00` : undefined })}
              className="rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none"
            />
          </label>
          <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
            Hasta
            <input
              type="date"
              value={borrador.hasta?.slice(0, 10) ?? ''}
              onChange={(e) => setCampo({ hasta: e.target.value ? `${e.target.value}T23:59:59` : undefined })}
              className="rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none"
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
            className="inline-flex items-center gap-2 px-4 py-2 rounded-md border border-surface-200 bg-white text-[14px] font-medium hover:bg-primary/5"
          >
            <Icon name="refresh" className="text-[16px]" /> Reintentar
          </button>
        </div>
      ) : cargando || !data ? (
        <div className="py-2xl flex items-center justify-center">
          <LoadingSpinner size="md" label="Cargando auditoría…" />
        </div>
      ) : data.items.length === 0 ? (
        <Card>
          <div className="py-xl flex flex-col items-center text-center gap-md text-on-surface-variant">
            <Icon name="history" className="text-[36px]" />
            <p className="text-[14px]">No hay actividad registrada para estos filtros.</p>
          </div>
        </Card>
      ) : (
        <>
          {/* Tarjetas de actividad, en columna vertical (una por acción). */}
          <div className="flex flex-col gap-3">
            {data.items.map((e) => {
              const meta = accionMeta(e.accion);
              const nombre = e.actor_nombre ?? e.actor;
              return (
                <div
                  key={e.id}
                  className="flex items-start gap-4 rounded-2xl border border-surface-200 bg-white px-6 py-5 shadow-card"
                >
                  {/* Ícono de la acción */}
                  <span
                    className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full"
                    style={{ backgroundColor: `${meta.color}1a`, color: meta.color }}
                    aria-hidden
                  >
                    <Icon name={meta.icon} className="text-[22px]" fill />
                  </span>

                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-3">
                      <span
                        className="inline-flex items-center rounded-full px-3 py-1 text-[12px] font-semibold"
                        style={{ backgroundColor: `${meta.color}1a`, color: meta.color }}
                      >
                        {meta.label}
                      </span>
                      <span className="shrink-0 text-[12.5px] text-on-surface-variant tabular-nums whitespace-nowrap">
                        {fmtFecha(e.timestamp)}
                      </span>
                    </div>

                    <p className="mt-2.5 text-[15px] font-semibold text-on-surface truncate" title={nombre}>
                      {nombre}
                    </p>
                    {e.actor_nombre && (
                      <p className="text-[12.5px] text-on-surface-variant truncate" title={e.actor}>
                        {e.actor}
                      </p>
                    )}
                    {e.proposito && <Proposito proposito={e.proposito} />}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Paginación (componente compartido: primera/última + página N de M). */}
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
