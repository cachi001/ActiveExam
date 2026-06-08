import type { ReactNode } from 'react';
import { useEffect, useState } from 'react';
import { StudentShell } from '../ui/shells';
import { Icon, Button, Card } from '../ui/components';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api } from '../lib/api';
import { Term } from '../ui/Term';

export default function Cierre() {
  const navigate = useNavigate();
  const anomalias = useApp((s) => s.anomaliasVivo);
  const score = useApp((s) => s.scorePropio);
  const examen = useApp((s) => s.examenActivo);
  const resetSesion = useApp((s) => s.resetSesion);
  const proctoringSessionId = useApp((s) => s.proctoringSessionId);

  // C-64 D4: conteos reales leídos del backend al montar (fuente de verdad).
  // Fallback: "—" si el GET falla o proctoringSessionId es null.
  const [totalEventos, setTotalEventos] = useState<number | null>(null);
  const [scoreBackend, setScoreBackend] = useState<number | null>(null);

  useEffect(() => {
    if (!proctoringSessionId) return;

    void (async () => {
      // 1. Finalizar la sesión (setea finalizada_en en el backend).
      await api.finalizarSesionProctoring(proctoringSessionId).catch(() => null);

      // 2. Leer conteos reales del backend.
      const detalle = await api.obtenerSesionProctoring(proctoringSessionId).catch(() => null);
      if (detalle) {
        setTotalEventos(detalle.total_eventos ?? null);
        setScoreBackend(detalle.score ?? null);
      }
    })();
  }, [proctoringSessionId]);

  const irARevision = (scoreBackend ?? score) >= (examen?.umbral_score ?? 70);

  const volver = () => { resetSesion(); navigate('/login'); };

  return (
    <StudentShell step={6}>
      <div className="max-w-xl mx-auto space-y-lg text-center animate-in zoom-in duration-500">
        <div className="w-20 h-20 rounded-full bg-success-container text-success flex items-center justify-center mx-auto">
          <Icon name="task_alt" className="text-[40px]" fill />
        </div>
        <div className="space-y-base">
          <h2 className="font-headline text-headline-lg text-on-surface">¡Examen finalizado!</h2>
          <p className="text-body-md text-on-surface-variant">
            Tu sesión se cerró con <Term termKey="cadena_de_custodia">cadena de custodia criptográfica</Term> server-side. La consolidación del score corre de forma asíncrona.
          </p>
        </div>

        <Card className="text-left space-y-sm">
          <h3 className="text-label-sm uppercase tracking-wide text-on-surface-variant border-b border-outline-variant/40 pb-base">Evidencia y firmas</h3>
          <Row label="Hash de sesión (SHA-256)" value={<code className="text-label-sm bg-surface-container px-base py-0.5 rounded font-mono">f92b8ac3e70d48bc93…</code>} />
          <Row label="Firma maestra (Ed25519)" value={<span className="text-success font-semibold inline-flex items-center gap-base"><Icon name="verified" className="text-[16px]" fill /> Válida y sellada</span>} />
          <Row label="Clave de sesión efímera" value={<span className="text-on-surface-variant italic">Liberada y eliminada</span>} />
          <Row
            label="Señales registradas"
            value={
              <span className="font-semibold">
                {totalEventos !== null ? totalEventos : anomalias.length}
              </span>
            }
          />
          <Row
            label="Score de prioridad"
            value={
              <span className="font-semibold">
                {scoreBackend !== null ? scoreBackend : score}%
              </span>
            }
          />
        </Card>

        <Card className={`text-left ${irARevision ? 'bg-warning-container/40 border-warning/30' : 'bg-success-container/40 border-success/30'}`}>
          <div className="flex items-start gap-sm">
            <Icon name={irARevision ? 'gavel' : 'verified_user'} className={irARevision ? 'text-warning' : 'text-success'} fill />
            <p className="text-label-md text-on-surface">
              {irARevision
                ? <>Tu sesión superó el umbral ({examen?.umbral_score}%) y entra a la cola de revisión académica. Recordá: el sistema no sanciona — la decisión es siempre humana.</>

                : 'Tu sesión no presenta incidencias relevantes. No se requiere revisión adicional.'}
            </p>
          </div>
        </Card>

        <p className="text-label-sm text-on-surface-variant px-md leading-relaxed">
          Tus datos biométricos se eliminan automáticamente a los 30 días del egreso, salvo que haya una apelación o proceso disciplinario abierto.
        </p>

        <Button variant="outline" icon="home" onClick={volver} className="mx-auto">Volver al inicio</Button>
      </div>
    </StudentShell>
  );
}

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex justify-between items-center gap-md">
      <span className="text-label-sm text-on-surface-variant">{label}</span>
      <span className="text-label-md text-on-surface text-right">{value}</span>
    </div>
  );
}
