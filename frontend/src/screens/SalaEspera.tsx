import { useEffect, useState } from 'react';
import { StudentShell } from '../ui/shells';
import { Icon, Button, Card } from '../ui/components';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { useAuth } from '../lib/authStore';
import { api } from '../lib/api';
import { nombreCompleto } from '../lib/types';

export default function SalaEspera() {
  const navigate = useNavigate();
  const principal = useAuth((s) => s.principal);
  const examen = useApp((s) => s.examenActivo);

  // Si catedra no está en el store (navegación directa o store stale),
  // la obtenemos del catálogo por examen_contenido_id.
  const [materiaFetched, setMateriaFetched] = useState<string | null>(null);

  useEffect(() => {
    const id = examen?.examen_contenido_id;
    if (!id || examen?.catedra) return;
    api.listarExamenesContenido().then((items) => {
      const found = items.find((i) => i.id === id);
      if (found?.materia_nombre) setMateriaFetched(found.materia_nombre);
    }).catch(() => {});
  }, [examen?.examen_contenido_id, examen?.catedra]);

  const materia = examen?.catedra || materiaFetched || '—';

  return (
    <StudentShell step={3} backTo="/biometria">
      <div className="max-w-xl lg:max-w-2xl mx-auto space-y-lg text-center animate-in zoom-in duration-500">
        <div className="w-20 h-20 rounded-full bg-success-container text-success flex items-center justify-center mx-auto">
          <Icon name="how_to_reg" className="text-[40px]" fill />
        </div>
        <div className="space-y-base">
          <h2 className="font-headline text-headline-lg text-on-surface">¡Identidad confirmada!</h2>
          <p className="text-body-md text-on-surface-variant">
            Tu identidad quedó confirmada de forma segura. Revisá los datos del examen
            y comenzá cuando estés listo.
          </p>
        </div>

        <Card className="text-left space-y-sm">
          <Row label="Examen" value={examen?.nombre ?? '—'} highlight />
          <Row label="Materia" value={materia} />
          <Row label="Estudiante" value={`${nombreCompleto(principal) || '—'} (${principal?.id_institucional ?? ''})`} />
          <Row label="Duración" value={examen?.duracion_min ? `${examen.duracion_min} minutos` : 'Sin límite'} />
          <div className="flex justify-between items-center pt-base border-t border-outline-variant/40">
            <span className="text-label-sm uppercase tracking-wide text-on-surface-variant">Supervisión</span>
            <span className="inline-flex items-center gap-xs text-success text-label-md font-semibold">
              <span className="w-2 h-2 rounded-full bg-success shrink-0" /> Lista
            </span>
          </div>
        </Card>

        <Button icon="play_arrow" onClick={() => navigate('/examen')} className="mx-auto">Comenzar examen</Button>

        <p className="text-label-sm text-on-surface-variant">
          Al comenzar, todo el análisis ocurre en tu propio dispositivo. No se graba tu examen: solo se avisa al equipo si se detecta algo para revisar.
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
