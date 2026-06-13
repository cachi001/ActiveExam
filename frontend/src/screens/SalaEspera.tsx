import { StudentShell } from '../ui/shells';
import { Icon, Button, Card } from '../ui/components';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { nombreCompleto } from '../lib/types';

export default function SalaEspera() {
  const navigate = useNavigate();
  const principal = useApp((s) => s.principal);
  const examen = useApp((s) => s.examenActivo);

  return (
    <StudentShell step={4}>
      <div className="max-w-xl mx-auto space-y-lg text-center animate-in zoom-in duration-500">
        <div className="w-20 h-20 rounded-full bg-success-container text-success flex items-center justify-center mx-auto">
          <Icon name="how_to_reg" className="text-[40px]" fill />
        </div>
        <div className="space-y-base">
          <h2 className="font-headline text-headline-lg text-on-surface">¡Identidad confirmada!</h2>
          <p className="text-body-md text-on-surface-variant">Tu acceso fue firmado con hash y clave de sesión efímera rotativa. Esperá la habilitación para comenzar.</p>
        </div>

        <Card className="text-left space-y-sm">
          <Row label="Examen" value={examen?.nombre ?? '—'} highlight />
          <Row label="Cátedra" value={examen?.catedra ?? '—'} />
          <Row label="Estudiante" value={`${nombreCompleto(principal) || '—'} (${principal?.id_institucional ?? ''})`} />
          <Row label="Duración" value={`${examen?.duracion_min ?? 0} minutos`} />
          <div className="flex justify-between items-center pt-base border-t border-outline-variant/40">
            <span className="text-label-sm uppercase tracking-wide text-on-surface-variant">Estado del monitor</span>
            <span className="inline-flex items-center gap-base text-success text-label-md font-semibold">
              <span className="w-2 h-2 rounded-full bg-success animate-ping" /> Web Worker de visión activo (local)
            </span>
          </div>
        </Card>

        <Button icon="play_arrow" onClick={() => navigate('/examen')} className="mx-auto">Comenzar examen</Button>

        <p className="text-label-sm text-on-surface-variant">
          Al comenzar, el análisis corre en tu navegador. Solo se envían señales firmadas y, ante incidencias graves, clips de evidencia.
        </p>
      </div>
    </StudentShell>
  );
}

function Row({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="flex justify-between items-center gap-md">
      <span className="text-label-sm uppercase tracking-wide text-on-surface-variant">{label}</span>
      <span className={`text-label-md font-semibold ${highlight ? 'text-primary' : 'text-on-surface'} text-right`}>{value}</span>
    </div>
  );
}
