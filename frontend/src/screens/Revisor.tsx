import { useEffect, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Icon, Button, Card, Avatar, Badge, SeverityBadge } from '../ui/components';
import { api, TIPO_EVENTO_LABEL } from '../lib/api';
import { useApp } from '../lib/store';
import { useNavigate } from '../lib/router';
import { STAFF_NAV } from '../ui/nav';
import type { SesionRevision } from '../lib/types';

export const REVISOR_NAV = STAFF_NAV;

export default function Revisor() {
  const [cola, setCola] = useState<SesionRevision[]>([]);
  const [sel, setSel] = useState<SesionRevision | null>(null);
  const setRevision = useApp((s) => s.setRevisionSeleccionada);
  const navigate = useNavigate();

  const cargar = () => api.reviewQueue().then((q) => { setCola(q); setSel((cur) => cur ?? q[0] ?? null); });
  useEffect(() => { cargar(); }, []);

  const resolver = async (decision: SesionRevision['decision'], etiqueta: string) => {
    if (!sel) return;
    await api.resolveReview(sel.id, decision);
    alert(`Sesión de ${sel.estudiante}: ${etiqueta}. Registrado en el audit log inmutable.`);
    const restantes = cola.filter((q) => q.id !== sel.id);
    setCola(restantes); setSel(restantes[0] ?? null);
  };

  return (
    <StaffShell nav={REVISOR_NAV} title="Revisión académica">
      <div className="grid lg:grid-cols-3 gap-lg">
        {/* Cola */}
        <Card className="space-y-sm">
          <div className="flex items-center justify-between border-b border-outline-variant/40 pb-base">
            <h2 className="font-headline text-title-lg text-on-surface">Cola de sesiones</h2>
            <Badge tone="error" dot>{cola.length} pendientes</Badge>
          </div>
          {cola.length === 0 && (
            <div className="text-center py-xl text-on-surface-variant space-y-base">
              <Icon name="inbox" className="text-[40px]" />
              <p className="text-label-md">¡Cola vacía! No hay sesiones flaggeadas pendientes.</p>
            </div>
          )}
          {cola.map((s) => (
            <button key={s.id} onClick={() => setSel(s)}
              className={`w-full text-left p-sm rounded-xl border transition-all ${sel?.id === s.id ? 'bg-primary-fixed/40 border-primary-container' : 'border-outline-variant/40 hover:bg-surface-container-low'}`}>
              <div className="flex gap-sm items-center">
                <Avatar src={s.foto} alt={s.estudiante} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-base">
                    <span className="text-label-md font-semibold text-on-surface truncate">{s.estudiante}</span>
                    <Badge tone="error">Score {s.score}%</Badge>
                  </div>
                  <p className="text-label-sm text-on-surface-variant">{s.examen} · {s.fecha}</p>
                  <p className="text-label-sm text-on-surface-variant mt-base">{s.id} · {s.eventos.length} incidencias</p>
                </div>
              </div>
            </button>
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
                    <p className="text-label-sm text-on-surface-variant">UBA Medicina · {sel.examen} · {sel.duracion}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-label-sm uppercase tracking-wide text-on-surface-variant">ID sesión</p>
                  <p className="font-mono text-label-md font-bold text-on-surface">{sel.id}</p>
                </div>
              </div>

              <div className="grid md:grid-cols-2 gap-lg">
                <div className="space-y-sm">
                  <h3 className="text-label-sm uppercase tracking-wide text-on-surface-variant border-b border-outline-variant/40 pb-base">Línea de tiempo de anomalías</h3>
                  {sel.eventos.map((ev) => (
                    <div key={ev.id} className="flex gap-sm p-sm rounded-xl bg-surface-container-low border border-outline-variant/40">
                      <Icon name="warning" className="text-warning shrink-0 text-[18px]" fill />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-base">
                          <span className="text-label-md font-semibold text-on-surface">{TIPO_EVENTO_LABEL[ev.tipo]}</span>
                          <SeverityBadge severidad={ev.severidad} />
                        </div>
                        <p className="text-label-sm text-on-surface-variant mt-base">{new Date(ev.ts_backend).toLocaleTimeString('es-AR')}</p>
                        {ev.tiene_evidencia && <code className="text-[10px] font-mono text-primary bg-primary-fixed px-base rounded">{ev.evidencia_object_key}</code>}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="space-y-sm">
                  <h3 className="text-label-sm uppercase tracking-wide text-on-surface-variant border-b border-outline-variant/40 pb-base">Evidencia y cadena de custodia</h3>
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

              <div className="bg-surface-container-low rounded-xl p-md space-y-md border border-outline-variant/40">
                <div>
                  <h3 className="font-headline text-title-lg text-on-surface">Resolución de auditoría humana (L2.5)</h3>
                  <p className="text-label-sm text-on-surface-variant mt-base">El software no sanciona automáticamente. Tu decisión es obligatoria y queda en el audit log inmutable.</p>
                </div>
                <div className="flex flex-col sm:flex-row gap-sm">
                  <Button variant="outline" className="flex-1" icon="thumb_up" onClick={() => resolver('descartada', 'descartada como falso positivo')}>Descartar (falso positivo)</Button>
                  <Button variant="outline" className="flex-1 text-warning border-warning/40" icon="search" onClick={() => resolver('escalada', 'escalada para investigación')}>Escalar (investigar)</Button>
                  <Button variant="danger" className="flex-1" icon="gavel" onClick={() => resolver('derivada', 'derivada a disciplina')}>Derivar a disciplina</Button>
                </div>
                <button onClick={() => { setRevision(sel); navigate('/revisor/detalle'); }} className="text-label-md text-primary hover:underline inline-flex items-center gap-base">
                  <Icon name="open_in_full" className="text-[18px]" /> Ver detalle forense completo
                </button>
              </div>
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
