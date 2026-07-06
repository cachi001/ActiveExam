import { useEffect, useState } from 'react';
import { StudentShell } from '../ui/shells';
import { Icon, Button } from '../ui/components';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api, TIPO_EVENTO_LABEL } from '../lib/api';
import type { ExamenContenidoResumen, TipoEvento } from '../lib/types';

function formatFecha(iso: string | null | undefined): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('es-AR', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

/** Ícono representativo por tipo de señal registrada (Material Symbols). */
const ICONO_EVENTO: Record<string, string> = {
  rostro_ausente: 'no_accounts',
  multiples_rostros: 'groups',
  mirada_desviada_sostenida: 'visibility',
  perdida_de_foco: 'flip_to_front',
  cambio_pestana: 'tab',
  monitor_adicional: 'devices',
  salida_pantalla_completa: 'fullscreen_exit',
  copiar_pegar: 'content_paste',
  corte_conectividad_prolongado: 'wifi_off',
};

export default function PreExamen() {
  const navigate = useNavigate();
  const examen = useApp((s) => s.examenActivo);
  const [contenido, setContenido] = useState<ExamenContenidoResumen | null>(null);
  // Señales que se registran (detectores activos de la config del sistema).
  const [detectores, setDetectores] = useState<string[]>([]);

  useEffect(() => {
    const id = examen?.examen_contenido_id;
    if (!id) return;
    api.listarExamenesContenido().then((items) => {
      const found = items.find((i) => i.id === id);
      if (found) setContenido(found);
    }).catch(() => {});
  }, [examen?.examen_contenido_id]);

  useEffect(() => {
    api.obtenerConfigEfectiva()
      .then((cfg) => setDetectores(cfg.detectores_activos ?? []))
      .catch(() => {});
  }, []);

  if (!examen) {
    return (
      <StudentShell>
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
      : 'Sin restricción';

  const ficha = [
    { icon: 'quiz', label: 'Preguntas', value: preguntasLabel },
    { icon: 'schedule', label: 'Tiempo límite', value: tiempoLabel },
    { icon: 'replay', label: 'Intentos permitidos', value: intentosLabel },
    { icon: 'calendar_today', label: 'Disponible', value: ventanaLabel },
  ];

  return (
    <StudentShell backTo="/alumno/mis-examenes">
      <div className="w-full space-y-lg animate-in fade-in duration-300">

        {/* Título */}
        <div className="space-y-xs">
          <p className="text-label-sm uppercase tracking-widest text-primary font-semibold">{materia}</p>
          <h1 className="font-headline text-headline-md text-on-surface">{titulo}</h1>
        </div>

        {/* Dos columnas: ficha + supervisión (izq) · panel de acción (der). Ocupa el ancho. */}
        <div className="grid lg:grid-cols-3 gap-lg items-start">

          {/* Izquierda */}
          <div className="lg:col-span-2 space-y-lg">
            {/* Ficha del examen — tabla simple, estilo institucional */}
            <div className="rounded-2xl border border-outline-variant/50 bg-white overflow-hidden divide-y divide-outline-variant/30">
              {ficha.map((f) => (
                <div key={f.label} className="flex items-center gap-md px-lg py-4">
                  <Icon name={f.icon} className="text-on-surface-variant text-[22px] shrink-0" />
                  <span className="text-body-md text-on-surface-variant flex-1">{f.label}</span>
                  <span className="text-body-lg font-semibold text-on-surface">{f.value}</span>
                </div>
              ))}
            </div>

            {/* Supervisión — las señales que se registran, como grilla de íconos (destacadas) */}
            <div className="rounded-2xl border border-primary/20 bg-primary-fixed/40 p-lg space-y-md">
              <div>
                <p className="text-label-md font-semibold text-on-surface">Examen supervisado</p>
                <p className="text-body-sm text-on-surface-variant mt-1">
                  Necesitás cámara y pantalla completa. Se registran estas señales para la revisión de un
                  docente — el sistema nunca sanciona solo.
                </p>
              </div>
              {detectores.length > 0 && (
                <div className="grid grid-cols-2 md:grid-cols-3 gap-sm">
                  {detectores.map((d) => (
                    <div
                      key={d}
                      className="flex items-center gap-sm p-sm rounded-xl bg-white border border-outline-variant/40"
                    >
                      <div className="w-8 h-8 rounded-lg bg-surface-container-high text-on-surface-variant flex items-center justify-center shrink-0">
                        <Icon name={ICONO_EVENTO[d] ?? 'visibility'} className="text-[18px]" />
                      </div>
                      <span className="text-label-md font-medium text-on-surface leading-tight">
                        {TIPO_EVENTO_LABEL[d as TipoEvento] ?? d}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Derecha: panel de acción */}
          <aside className="lg:sticky lg:top-6">
            <div className="rounded-2xl border border-outline-variant/50 bg-white p-lg space-y-md text-center">
              <div className="w-14 h-14 rounded-full bg-primary-fixed text-primary flex items-center justify-center mx-auto">
                <Icon name="assignment_turned_in" className="text-[28px]" />
              </div>
              <div className="space-y-xs">
                <p className="text-title-md font-bold text-on-surface">Todo listo para rendir</p>
                <p className="text-body-sm text-on-surface-variant">
                  {preguntasLabel} preguntas · {tiempoLabel} · {intentosLabel} {intentosLabel === '1' ? 'intento' : 'intentos'}
                </p>
              </div>
              <Button icon="play_arrow" onClick={() => navigate('/requisitos')} className="w-full">
                Comenzar examen
              </Button>
              <button
                onClick={() => navigate('/alumno/mis-examenes')}
                className="text-label-md text-primary hover:underline w-full"
              >
                Volver
              </button>
              <p className="text-label-xs text-on-surface-variant">
                Una vez que iniciés, el tiempo no se pausa.
              </p>
            </div>
          </aside>

        </div>
      </div>
    </StudentShell>
  );
}
