import { useEffect, useState } from 'react';
import { StudentShell } from '../ui/shells';
import { Icon, Button, Card } from '../ui/components';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api, TIPO_EVENTO_LABEL, descripcionEvento } from '../lib/api';
import type { ExamenContenidoResumen, TipoEvento } from '../lib/types';

function formatFecha(iso: string | null | undefined): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('es-AR', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function InfoCard({ icon, label, value }: { icon: string; label: string; value: string }) {
  return (
    <div className="flex flex-col items-center gap-sm p-md bg-surface-container-low rounded-xl text-center">
      <div className="w-10 h-10 rounded-full bg-primary-fixed text-primary flex items-center justify-center">
        <Icon name={icon} className="text-[20px]" />
      </div>
      <p className="text-label-sm uppercase tracking-wide text-on-surface-variant">{label}</p>
      <p className="text-label-md font-bold text-on-surface">{value}</p>
    </div>
  );
}

export default function PreExamen() {
  const navigate = useNavigate();
  const examen = useApp((s) => s.examenActivo);
  const [contenido, setContenido] = useState<ExamenContenidoResumen | null>(null);
  // Detectores activos de la config del sistema → eventos que se registrarán.
  const [detectores, setDetectores] = useState<string[]>([]);

  useEffect(() => {
    const id = examen?.examen_contenido_id;
    if (!id) return;
    api.listarExamenesContenido().then((items) => {
      const found = items.find((i) => i.id === id);
      if (found) setContenido(found);
    }).catch(() => {});
  }, [examen?.examen_contenido_id]);

  // Qué eventos se registran durante el examen (config efectiva del sistema).
  useEffect(() => {
    api.obtenerConfigEfectiva()
      .then((cfg) => setDetectores(cfg.detectores_activos ?? []))
      .catch(() => {});
  }, []);

  if (!examen) {
    return (
      <StudentShell step={4}>
        <div className="flex items-center justify-center min-h-64 text-on-surface-variant">
          Cargando información del examen…
        </div>
      </StudentShell>
    );
  }

  const titulo = contenido?.titulo ?? examen.nombre;
  const materia = contenido?.materia_nombre ?? examen.catedra ?? '—';
  const tiempoLabel = contenido?.tiempo_limite_min
    ? `${contenido.tiempo_limite_min} min`
    : examen.duracion_min
    ? `${examen.duracion_min} min`
    : 'Sin límite';
  const preguntasLabel = contenido?.cantidad_preguntas ? `${contenido.cantidad_preguntas}` : '—';
  const intentosLabel = contenido?.intentos_permitidos ? `${contenido.intentos_permitidos}` : '1';
  const ventanaLabel =
    contenido?.apertura && contenido?.cierre
      ? `${formatFecha(contenido.apertura)} – ${formatFecha(contenido.cierre)}`
      : contenido?.apertura
      ? `Desde ${formatFecha(contenido.apertura)}`
      : 'Abierta';

  return (
    <StudentShell step={4} backTo="/sala-espera">
      <div className="max-w-3xl mx-auto space-y-lg animate-in fade-in duration-300">

        <div className="text-center space-y-base">
          <p className="text-label-sm uppercase tracking-widest text-primary font-semibold">{materia}</p>
          <h1 className="font-headline text-headline-md text-on-surface">{titulo}</h1>
          <p className="text-body-md text-on-surface-variant">
            Revisá la información antes de comenzar. Una vez que iniciés, no podés pausar el tiempo.
          </p>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-sm">
          <InfoCard icon="schedule" label="Tiempo" value={tiempoLabel} />
          <InfoCard icon="quiz" label="Preguntas" value={preguntasLabel} />
          <InfoCard icon="replay" label="Intentos" value={intentosLabel} />
          <InfoCard icon="calendar_today" label="Ventana" value={ventanaLabel} />
        </div>

        {detectores.length > 0 && (
          <Card className="space-y-sm">
            <div className="flex items-center gap-sm">
              <Icon name="visibility" className="text-primary text-[20px]" fill />
              <p className="text-label-md font-bold text-on-surface">Qué se registra durante el examen</p>
            </div>
            <p className="text-body-sm text-on-surface-variant">
              La supervisión es automática. Se registran estas señales para la revisión humana posterior
              (el sistema nunca sanciona solo):
            </p>
            <ul className="grid sm:grid-cols-2 gap-sm">
              {detectores.map((d) => (
                <li key={d} className="flex items-start gap-sm p-sm rounded-lg bg-surface-container-low">
                  <Icon name="fiber_manual_record" className="text-primary text-[10px] shrink-0 mt-1.5" fill />
                  <div className="min-w-0">
                    <p className="text-label-md font-semibold text-on-surface">{TIPO_EVENTO_LABEL[d as TipoEvento] ?? d}</p>
                    <p className="text-[12px] text-on-surface-variant leading-snug">{descripcionEvento(d as TipoEvento)}</p>
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        )}

        <Card className="space-y-sm bg-secondary-container/40 border-secondary/20">
          <div className="flex items-center gap-sm">
            <Icon name="info" className="text-primary text-[20px]" fill />
            <p className="text-label-md font-bold text-on-surface">Antes de comenzar</p>
          </div>
          <ul className="space-y-sm text-body-sm text-on-surface-variant pl-sm">
            {[
              'Vas a necesitar cámara habilitada y pantalla completa durante todo el examen.',
              'Salir de pantalla completa queda registrado como señal de supervisión.',
              'La supervisión es automática — la revisión final siempre la hace una persona del equipo.',
              'Podés navegar entre preguntas y cambiar tus respuestas antes de entregar.',
            ].map((item) => (
              <li key={item} className="flex items-start gap-sm">
                <Icon name="check_circle" className="text-success text-[16px] shrink-0 mt-0.5" fill />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </Card>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-md pt-sm">
          <button
            onClick={() => navigate('/sala-espera')}
            className="text-label-md text-primary hover:underline flex items-center gap-xs"
          >
            <Icon name="arrow_back" className="text-[16px]" /> Volver
          </button>
          <Button icon="play_arrow" onClick={() => navigate('/examen')} className="sm:px-xl">
            Comenzar examen
          </Button>
        </div>

      </div>
    </StudentShell>
  );
}
