import { useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Icon, Card, Avatar, Badge, SeverityBadge, Button, Stat, SectionTitle } from '../ui/components';
import { REVISOR_NAV } from './Revisor';
import { useApp } from '../lib/store';
import { useNavigate } from '../lib/router';
import { TIPO_EVENTO_LABEL } from '../lib/api';
import { Term } from '../ui/Term';

export default function SessionDetail() {
  const sel = useApp((s) => s.revisionSeleccionada);
  const navigate = useNavigate();

  if (!sel) {
    return (
      <StaffShell nav={REVISOR_NAV} title="Detalle de sesión">
        <Card className="text-center py-xl space-y-md">
          <Icon name="description" className="text-outline text-[48px]" />
          <p className="text-body-md text-on-surface-variant">Seleccioná una sesión desde la cola de revisión.</p>
          <Button icon="gavel" onClick={() => navigate('/revisor')} className="mx-auto">Ir a la cola</Button>
        </Card>
      </StaffShell>
    );
  }

  return (
    <StaffShell nav={REVISOR_NAV} title={`Detalle de sesión · ${sel.id}`}>
      <div className="space-y-lg">
        <Card className="flex flex-wrap items-center justify-between gap-md">
          <div className="flex items-center gap-md">
            <Avatar src={sel.foto} alt={sel.estudiante} size={64} />
            <div>
              <h2 className="font-headline text-headline-md text-on-surface">{sel.estudiante}</h2>
              <p className="text-label-md text-on-surface-variant">Legajo {sel.legajo} · {sel.examen} ({sel.catedra})</p>
            </div>
          </div>
          <Badge tone="error" dot>Score de prioridad {sel.score}%</Badge>
        </Card>

        <div className="grid sm:grid-cols-3 gap-lg">
          <Stat icon="schedule" label="Duración" value={sel.duracion} />
          <Stat icon="event" label="Fecha" value={sel.fecha} />
          <Stat icon="warning" label="Incidencias" value={sel.eventos.length} sub={`${sel.eventos.filter((e) => e.tiene_evidencia).length} con evidencia`} />
        </div>

        <div className="grid lg:grid-cols-2 gap-lg">
          <Card className="space-y-sm">
            <SectionTitle sub={`${sel.eventos.length} evento${sel.eventos.length !== 1 ? 's' : ''}`}>Eventos discretos</SectionTitle>
            {sel.eventos.map((ev) => (
              <div key={ev.id} className="flex items-center justify-between gap-sm p-sm rounded-xl bg-surface-container-low border border-outline-variant/40">
                <div className="flex items-center gap-sm">
                  <Icon name="bolt" className="text-warning" fill />
                  <div>
                    <p className="text-label-md font-semibold text-on-surface">{TIPO_EVENTO_LABEL[ev.tipo]}</p>
                    <p className="text-label-sm text-on-surface-variant">{new Date(ev.ts_backend).toLocaleString('es-AR')}</p>
                  </div>
                </div>
                <SeverityBadge severidad={ev.severidad} />
              </div>
            ))}
          </Card>

          {/* task 7.1: cadena de custodia colapsable; task 7.2: abierta en desktop, cerrada en mobile */}
          <Card className="space-y-sm">
            {/* La clase `ae-cadena-open` se usa como anchor; el open por defecto en ≥1024px
                se logra con el atributo HTML en un wrapper details que aplica lg:open via CSS */}
            <details className="ae-cadena-details" {...{} as React.DetailsHTMLAttributes<HTMLElement>}>
              <summary className="cursor-pointer select-none list-none flex items-center justify-between gap-sm border-b border-outline-variant/40 pb-base">
                <h3 className="text-label-sm uppercase tracking-wide text-on-surface-variant">
                  <Term termKey="cadena_de_custodia">Cadena de custodia criptográfica</Term>
                </h3>
                <Icon name="expand_more" className="text-on-surface-variant text-[18px] ae-cadena-chevron" />
              </summary>
              <div className="space-y-sm pt-sm">
                <CadenaPaso n={1} titulo="Cliente (navegador)" desc={`Hash del clip: ${sel.cadena_custodia.hash_cliente}`} icon="laptop" />
                <CadenaPaso n={2} titulo="Backend (FastAPI)" desc={`Re-hash: ${sel.cadena_custodia.rehash_backend} · ${sel.cadena_custodia.coincide ? 'coincide' : 'divergencia'}`} icon="dns" ok={sel.cadena_custodia.coincide} />
                <CadenaPaso n={3} titulo="Worker / clave maestra" desc={`Firma ${sel.cadena_custodia.algoritmo_firma}: ${sel.cadena_custodia.firma_maestra}`} icon="key" ok />
                <CadenaPaso n={4} titulo="Re-inferencia server-side" desc="Señales re-evaluadas sobre la evidencia exacta." icon="neurology" ok />
                <div className="bg-primary-fixed/40 rounded-xl p-sm text-label-sm text-on-primary-fixed-variant flex items-start gap-base">
                  <Icon name="info" className="text-[18px]" fill />
                  <span>El cliente es un sensor no confiable: toda evidencia se re-hashea, re-infiere y firma del lado del servidor.</span>
                </div>
              </div>
            </details>
          </Card>
        </div>

        <div className="flex gap-sm">
          <Button variant="outline" icon="arrow_back" onClick={() => navigate('/revisor')}>Volver a la cola</Button>
          <Button icon="download">Exportar dossier firmado</Button>
        </div>
      </div>
    </StaffShell>
  );
}

/** task 7.3: trunca el primer hash largo encontrado en `desc` a 12 caracteres + toggle. */
function CadenaPaso({ n, titulo, desc, icon, ok }: { n: number; titulo: string; desc: string; icon: string; ok?: boolean }) {
  const [hashExpanded, setHashExpanded] = useState(false);

  // Detecta si desc contiene un hash largo (más de 20 chars seguidos sin espacio)
  // y lo trunca mostrando solo los primeros 12 caracteres + "..." + botón "ver completo".
  const HASH_RE = /([a-f0-9A-F+/=]{20,})/;
  const match = desc.match(HASH_RE);
  let displayDesc: React.ReactNode = desc;
  if (match) {
    const full = match[1];
    const truncated = full.slice(0, 12) + '…';
    const before = desc.slice(0, desc.indexOf(full));
    const after = desc.slice(desc.indexOf(full) + full.length);
    displayDesc = (
      <>
        {before}
        <span className="font-mono">{hashExpanded ? full : truncated}</span>
        {' '}
        <button
          type="button"
          onClick={() => setHashExpanded((v) => !v)}
          className="text-primary hover:underline text-[11px]"
        >
          {hashExpanded ? 'ocultar' : 'ver completo'}
        </button>
        {after}
      </>
    );
  }

  return (
    <div className="flex items-start gap-sm p-sm rounded-xl bg-surface-container-low border border-outline-variant/40">
      <div className="w-8 h-8 rounded-full bg-primary text-on-primary flex items-center justify-center text-label-sm font-bold shrink-0">{n}</div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-base">
          <Icon name={icon} className="text-on-surface-variant text-[18px]" />
          <span className="text-label-md font-semibold text-on-surface">{titulo}</span>
          {ok && <Icon name="check_circle" className="text-success text-[16px]" fill />}
        </div>
        <p className="text-label-sm text-on-surface-variant mt-base break-all">{displayDesc}</p>
      </div>
    </div>
  );
}
