import { useEffect, useMemo, useRef, useState } from 'react';
import { StudentShell } from '../ui/shells';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api } from '../lib/api';
import { useExamProctoring } from '../proctoring/useExamProctoring';
import { getEffectiveConfig, loadEffectiveConfig } from '../config/effectiveConfigCache';
import type { EventoSesion } from '../lib/types';
import { fetchExamenParaRendir } from '../lib/examTakingApi';
import type { ExamenRendicion } from '../lib/examTakingApi';
import {
  avanzarPregunta,
  retrocederPregunta,
  preguntaEnIndice,
  indicesRespondidos,
  mezclarConSemilla,
} from './ExamenLogic';
import { FullscreenLockdown } from '../proctoring/fullscreenLockdown';
import { MonitorBloqueante } from './examen/MonitorBloqueante';
import { AlertaCritica } from './examen/AlertaCritica';
import { LockdownOverlay } from './examen/LockdownOverlay';
import { ExamenPreguntaCard } from './examen/ExamenPreguntaCard';
import { ExamenCamaraPanel } from './examen/ExamenCamaraPanel';
import { IntegridadPanel } from './examen/IntegridadPanel';
import { QuestionNavigator } from './alumno/components/QuestionNavigator';
import { PausaAlumno } from './PausaAlumno';
import { ChatBox } from '../ui/ChatBox';
import { Card } from '../ui/components';

export default function Examen() {
  const navigate = useNavigate();
  const examen = useApp((s) => s.examenActivo);

  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const [tiempoLimiteMin, setTiempoLimiteMin] = useState<number | null | undefined>(undefined);
  const [segRestantes, setSegRestantes] = useState<number | null>(null);
  const [alerta, setAlerta] = useState<EventoSesion | null>(null);
  const [pausaActiva, setPausaActiva] = useState(false);

  const [preguntasRaw, setPreguntasRaw] = useState<ExamenRendicion['preguntas']>([]);
  const [mezclar, setMezclar] = useState(false);
  const [cargandoPreguntas, setCargandoPreguntas] = useState(false);
  const entregadoRef = useRef(false);
  const [indiceActual, setIndiceActual] = useState(0);
  const [respuestas, setRespuestas] = useState<Record<string, string>>({});

  const [bloqueado, setBloqueado] = useState(false);
  const lockdownRef = useRef<FullscreenLockdown | null>(null);

  const [chatHabilitado, setChatHabilitado] = useState(true);
  const [pausasHabilitadas, setPausasHabilitadas] = useState(true);
  useEffect(() => {
    void loadEffectiveConfig().then(() => {
      const cfg = getEffectiveConfig();
      if (cfg) {
        setChatHabilitado(cfg.chat_habilitado);
        setPausasHabilitadas(cfg.pausas_habilitadas);
      }
    });
  }, []);

  const { sessionId, score, eventCount, activo, eventos, extraMonitorActive, detener } = useExamProctoring(videoRef, examen);

  useEffect(() => {
    navigator.mediaDevices?.getUserMedia({ video: true }).then((s) => {
      streamRef.current = s;
      if (videoRef.current) { videoRef.current.srcObject = s; videoRef.current.play().catch(() => {}); }
    }).catch(() => {});
    return () => streamRef.current?.getTracks().forEach((t) => t.stop());
  }, []);

  useEffect(() => {
    const t = setInterval(
      () => setSegRestantes((s) => (s === null ? null : s <= 0 ? 0 : s - 1)),
      1000,
    );
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const examenContenidoId = examen?.examen_contenido_id;
    if (!examenContenidoId) return;
    setCargandoPreguntas(true);
    fetchExamenParaRendir(examenContenidoId)
      .then((data) => {
        if (!data) return;
        setPreguntasRaw(data.preguntas);
        setMezclar(!!data.mezclar_preguntas);
        const tl = data.tiempo_limite_min ?? null;
        setTiempoLimiteMin(tl);
        setSegRestantes(tl !== null && tl > 0 ? tl * 60 : null);
      })
      .catch(() => {})
      .finally(() => setCargandoPreguntas(false));
  }, [examen?.examen_contenido_id]);

  const lastAlertaId = useRef<string | null>(null);
  useEffect(() => {
    const critico = eventos.find(
      (e) => (e.severidad === 'alta' || e.severidad === 'critica') && e.tipo !== 'monitor_adicional',
    );
    if (critico && critico.id !== lastAlertaId.current) {
      lastAlertaId.current = critico.id;
      setAlerta(critico);
    }
  }, [eventos]);

  useEffect(() => {
    const lockdown = new FullscreenLockdown(
      (state) => setBloqueado(state.bloqueado),
      (_tipo) => {},
    );
    lockdownRef.current = lockdown;
    lockdown.iniciar().catch(() => {});
    return () => lockdown.detener();
  }, []);

  const finalizar = async () => {
    if (entregadoRef.current) return;
    entregadoRef.current = true;
    try {
      if (sessionId) {
        const items = Object.entries(respuestas).map(([pregunta_id, opcion_elegida_id]) => ({
          pregunta_id,
          opcion_elegida_id,
        }));
        await api.enviarRespuestasProctoring(sessionId, items);
      }
    } catch {
      // degradación silenciosa
    } finally {
      detener();
      navigate('/cierre');
    }
  };

  useEffect(() => {
    if (segRestantes === 0 && typeof tiempoLimiteMin === 'number' && tiempoLimiteMin > 0) {
      void finalizar();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [segRestantes, tiempoLimiteMin]);

  const seedMezcla = sessionId ?? examen?.examen_contenido_id ?? examen?.id ?? 'sin-sesion';
  const preguntas = useMemo(
    () => (mezclar ? mezclarConSemilla(preguntasRaw, seedMezcla) : preguntasRaw),
    [preguntasRaw, mezclar, seedMezcla],
  );

  const total = preguntas.length;
  const preguntaActual = preguntaEnIndice(preguntas, indiceActual);
  const respondidas = indicesRespondidos(preguntas, respuestas);

  return (
    <StudentShell locked>
      <div className={`w-full animate-in fade-in duration-500 transition-[padding] ${pausaActiva ? 'pt-16' : ''}`}>

        {/* Cámara grande + Integridad, arriba (ocupan el ancho) */}
        <div className="flex flex-col lg:flex-row gap-md items-stretch mb-lg">
          <div className="w-full lg:w-[560px] shrink-0">
            <ExamenCamaraPanel videoRef={videoRef} />
          </div>
          <div className="flex-1 min-w-0">
            <IntegridadPanel
              activo={activo}
              eventCount={eventCount}
              score={score}
              eventos={eventos}
              examen={examen}
            />
          </div>
        </div>

        <div className="space-y-lg">
          {/* Pregunta (timer + progreso dentro de la card) */}
          <ExamenPreguntaCard
            preguntaActual={preguntaActual}
            indiceActual={indiceActual}
            total={total}
            cargandoPreguntas={cargandoPreguntas}
            respuestas={respuestas}
            respondidas={respondidas}
            segRestantes={segRestantes}
            tiempoLimiteMin={tiempoLimiteMin}
            onSeleccionarOpcion={(pid, oid) => setRespuestas((prev) => ({ ...prev, [pid]: oid }))}
            onAnterior={() => setIndiceActual((i) => retrocederPregunta(i))}
            onSiguiente={() => setIndiceActual((i) => avanzarPregunta(i, total))}
            onFinalizar={finalizar}
          />

          {/* Navegador de preguntas (números centrados) */}
          {total > 0 && (
            <Card className="space-y-sm">
              <h3 className="text-label-sm font-semibold text-on-surface-variant uppercase tracking-wide">
                Preguntas
              </h3>
              <QuestionNavigator
                total={total}
                indiceActual={indiceActual}
                respondidas={respondidas}
                onIr={setIndiceActual}
              />
            </Card>
          )}

          {/* Chat con el proctor + pausas — debajo de las preguntas */}
          {(pausasHabilitadas || chatHabilitado) && (
            <div className="grid md:grid-cols-2 gap-md items-start">
              {pausasHabilitadas && (
                <PausaAlumno sessionId={sessionId} onActivaChange={setPausaActiva} />
              )}
              {chatHabilitado && (
                <ChatBox sessionId={sessionId} yo="alumno" titulo="Canal con el proctor" altura="h-[160px]" />
              )}
            </div>
          )}
        </div>
      </div>

      {alerta && <AlertaCritica ev={alerta} onClose={() => setAlerta(null)} />}
      {extraMonitorActive && <MonitorBloqueante />}
      {bloqueado && (
        <LockdownOverlay onVolverAPantallaCompleta={() => lockdownRef.current?.volverAPantallaCompleta()} />
      )}
    </StudentShell>
  );
}
