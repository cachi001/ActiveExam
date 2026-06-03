import { useEffect, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Icon, Card, Avatar, Badge, SeverityBadge, SectionTitle } from '../ui/components';
import { api, TIPO_EVENTO_LABEL } from '../lib/api';
import { useApp } from '../lib/store';
import { useNavigate } from '../lib/router';
import { STAFF_NAV } from '../ui/nav';
import { useToast } from '../ui/toast';
import { Term } from '../ui/Term';
import type { SesionRevision } from '../lib/types';
import { INSTITUTION } from '../config/institution';
import { ReviewQueueItem } from './admin/components/ReviewQueueItem';
import { ReviewDecisionPanel } from './admin/components/ReviewDecisionPanel';

export const REVISOR_NAV = STAFF_NAV;

export default function Revisor() {
  const [cola, setCola] = useState<SesionRevision[]>([]);
  const [sel, setSel] = useState<SesionRevision | null>(null);
  const setRevision = useApp((s) => s.setRevisionSeleccionada);
  const navigate = useNavigate();
  const toast = useToast();

  const cargar = () => api.reviewQueue().then((q) => { setCola(q); setSel((cur) => cur ?? q[0] ?? null); });
  useEffect(() => { cargar(); }, []);

  const resolver = async (decision: SesionRevision['decision'], etiqueta: string) => {
    if (!sel) return;
    await api.resolveReview(sel.id, decision);
    toast.success(`Sesión de ${sel.estudiante}: ${etiqueta}. Registrado en el audit log inmutable.`);
    const restantes = cola.filter((q) => q.id !== sel.id);
    setCola(restantes); setSel(restantes[0] ?? null);
  };

  return (
    <StaffShell nav={REVISOR_NAV} title="Revisión académica">
      <div className="space-y-lg animate-in fade-in duration-500">
        {/* Header */}
        <div className="flex items-start justify-between gap-md flex-wrap">
          <div>
            <h1 className="font-headline text-headline-md text-on-surface tracking-tight">
              Cola de revisión humana
            </h1>
            <p className="text-body-md text-on-surface-variant mt-base">
              Sesiones priorizadas por score. El sistema nunca sanciona: la decisión es siempre tuya.
            </p>
          </div>
          <div className="flex items-center gap-base px-sm py-base rounded-lg bg-primary-fixed/50
            border border-primary/20 text-label-sm text-on-primary-fixed-variant">
            <Icon name="shield" className="text-[16px] shrink-0" fill />
            <span>Decisión humana</span>
          </div>
        </div>

        <div className="grid lg:grid-cols-3 gap-lg">
        {/* Cola */}
        <Card className="space-y-base">
          <SectionTitle action={<Badge tone="error" dot>{cola.length} pendientes</Badge>}>Cola de sesiones</SectionTitle>
          {cola.length === 0 && (
            <div className="text-center py-xl text-on-surface-variant space-y-base">
              <Icon name="inbox" className="text-[40px]" />
              <p className="text-label-md">¡Cola vacía! No hay sesiones flaggeadas pendientes.</p>
            </div>
          )}
          {cola.map((s) => (
            <ReviewQueueItem key={s.id} sesion={s} selected={sel?.id === s.id} onClick={() => setSel(s)} />
          ))}
        </Card>

        {/* Detalle + decisión */}
        <div className="lg:col-span-2">
          {sel ? (
            <Card className="space-y-lg">
              <div className="flex items-center justify-between border-b border-outline-variant/40 pb-md">
                <div className="flex items-center gap-sm">
                  <Avatar src={sel.foto} alt={sel.estudiante} size={56} />
                  <div>
                    <h2 className="font-headline text-headline-md text-on-surface">{sel.estudiante}</h2>
                    <p className="text-label-sm text-on-surface-variant">{INSTITUTION.nombreCorto} · {sel.examen} · {sel.duracion}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-label-sm uppercase tracking-wide text-on-surface-variant">ID sesión</p>
                  <p className="font-mono text-label-md font-bold text-on-surface">{sel.id}</p>
                </div>
              </div>

              <div className="grid md:grid-cols-2 gap-lg">
                <div className="space-y-sm">
                  <SectionTitle sub={`${sel.eventos.length} incidencias`}>Línea de tiempo de anomalías</SectionTitle>
                  {/* task 8.1: p-md en cada item; tasks 8.2–8.3: agrupación de ≥5 consecutivos del mismo tipo */}
                  {groupConsecutiveEvents(sel.eventos).map((group) => {
                    const ev = group.first;
                    const isGrouped = group.count >= 5;
                    return (
                      <div key={ev.id} className="flex gap-sm p-md rounded-xl bg-surface-container-low border border-outline-variant/40">
                        <Icon name="warning" className="text-warning shrink-0 text-[18px]" fill />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center justify-between gap-base flex-wrap">
                            <div className="flex items-center gap-sm flex-wrap">
                              <span className="text-label-md font-semibold text-on-surface">{TIPO_EVENTO_LABEL[ev.tipo]}</span>
                              {isGrouped && (
                                <span className="inline-flex items-center gap-base px-sm py-base rounded-full bg-warning-container text-warning text-label-sm font-bold border border-warning/30">
                                  {group.count} veces
                                </span>
                              )}
                            </div>
                            <SeverityBadge severidad={ev.severidad} />
                          </div>
                          <p className="text-label-sm text-on-surface-variant mt-base">{new Date(ev.ts_backend).toLocaleTimeString('es-AR')}</p>
                          {ev.tiene_evidencia && <code className="text-[10px] font-mono text-primary bg-primary-fixed px-base rounded">{ev.evidencia_object_key}</code>}
                        </div>
                      </div>
                    );
                  })}
                </div>

                <div className="space-y-sm">
                  <SectionTitle>Evidencia y <Term termKey="cadena_de_custodia">cadena de custodia</Term></SectionTitle>
                  <div className="relative aspect-video bg-inverse-surface rounded-xl overflow-hidden flex items-center justify-center">
                    <img src={sel.foto} alt="evidencia" className="absolute inset-0 w-full h-full object-cover opacity-30 blur-[2px]" />
                    <button className="relative z-10 w-12 h-12 rounded-full bg-white/15 backdrop-blur ring-2 ring-white/30 flex items-center justify-center text-white hover:bg-white/25">
                      <Icon name="play_arrow" className="text-[28px]" fill />
                    </button>
                  </div>
                  <div className="bg-surface-container-low rounded-xl p-sm space-y-base text-label-sm">
                    <Custodia label="Hash de custodia (cliente)" value={sel.cadena_custodia.hash_cliente} ok />
                    <Custodia label="Re-hash server (FastAPI)" value={sel.cadena_custodia.rehash_backend} ok={sel.cadena_custodia.coincide} />
                    <div className="flex justify-between">
                      <span className="text-on-surface-variant">Firma maestra ({sel.cadena_custodia.algoritmo_firma})</span>
                      <span className="text-success font-semibold inline-flex items-center gap-base"><Icon name="verified" className="text-[16px]" fill /> Firmada</span>
                    </div>
                  </div>
                </div>
              </div>

              <ReviewDecisionPanel sesion={sel} onResolver={resolver} onVerDetalle={() => { setRevision(sel); navigate('/revisor/detalle'); }} />
            </Card>
          ) : (
            <Card className="text-center py-xl space-y-base">
              <Icon name="task_alt" className="text-success text-[48px]" fill />
              <h3 className="font-headline text-title-lg text-on-surface">¡Cola vacía!</h3>
              <p className="text-body-md text-on-surface-variant">No hay más sesiones flaggeadas pendientes de revisión.</p>
            </Card>
          )}
        </div>
        </div>
      </div>
    </StaffShell>
  );
}

function Custodia({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-on-surface-variant">{label}</span>
      <span className="inline-flex items-center gap-base font-mono text-on-surface">
        {value} <Icon name={ok ? 'check_circle' : 'error'} className={`text-[14px] ${ok ? 'text-success' : 'text-error'}`} fill />
      </span>
    </div>
  );
}

/**
 * task 8.2–8.3: Agrupa eventos CONSECUTIVOS del mismo tipo cuando hay ≥5 seguidos.
 * Solo agrupa consecutivos, no todos los del mismo tipo en la sesión.
 */
interface EventGroup {
  first: SesionRevision['eventos'][number];
  count: number;
}

function groupConsecutiveEvents(eventos: SesionRevision['eventos']): EventGroup[] {
  if (eventos.length === 0) return [];
  const groups: EventGroup[] = [];
  let current: EventGroup = { first: eventos[0], count: 1 };

  for (let i = 1; i < eventos.length; i++) {
    if (eventos[i].tipo === current.first.tipo) {
      current.count++;
    } else {
      groups.push(current);
      current = { first: eventos[i], count: 1 };
    }
  }
  groups.push(current);
  return groups;
}
