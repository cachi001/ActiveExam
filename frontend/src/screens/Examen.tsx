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
import { ProctoringPanel } from './examen/ProctoringPanel';
import { ExamenTopBar } from './examen/ExamenTopBar';
import { ExamenCamaraPanel } from './examen/ExamenCamaraPanel';
import { QuestionNavigator } from './alumno/components/QuestionNavigator';
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
      <div className={`mx-auto w-full max-w-[1500px] animate-in fade-in duration-500 transition-[padding] ${pausaActiva ? 'pt-16' : ''}`}>

        {/* Barra superior sticky: progreso + timer (la cámara vive en el sidebar) */}
        <ExamenTopBar
          indiceActual={indiceActual}
          total={total}
          respondidas={respondidas}
          tiempoLimiteMin={tiempoLimiteMin}
          segRestantes={segRestantes}
          stickyOffsetClass={pausaActiva ? 'top-16' : 'top-0'}
        />

        <div className="flex flex-col lg:flex-row gap-lg items-start">
          {/* Pregunta: columna principal, ocupa todo el ancho libre */}
          <main className="flex-1 min-w-0 w-full">
            <ExamenPreguntaCard
              preguntaActual={preguntaActual}
              indiceActual={indiceActual}
              total={total}
              cargandoPreguntas={cargandoPreguntas}
              respuestas={respuestas}
              onSeleccionarOpcion={(pid, oid) => setRespuestas((prev) => ({ ...prev, [pid]: oid }))}
              onAnterior={() => setIndiceActual((i) => retrocederPregunta(i))}
              onSiguiente={() => setIndiceActual((i) => avanzarPregunta(i, total))}
              onFinalizar={finalizar}
            />
          </main>

          {/* Sidebar: cámara grande + navegador de preguntas + integridad + pausa/chat.
              Sticky para seguir visible al scrollear. */}
          <aside className="w-full lg:w-[380px] shrink-0 lg:sticky lg:top-24 space-y-md">
            <ExamenCamaraPanel videoRef={videoRef} activo={activo} eventCount={eventCount} />

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

            <ProctoringPanel
              activo={activo}
              eventCount={eventCount}
              score={score}
              eventos={eventos}
              examen={examen}
              sessionId={sessionId}
              chatHabilitado={chatHabilitado}
              pausasHabilitadas={pausasHabilitadas}
              onActivaChange={setPausaActiva}
            />
          </aside>
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
