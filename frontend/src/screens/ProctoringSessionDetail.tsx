/**
 * ProctoringSessionDetail — Detalle completo de una sesión de proctoring (C-46).
 *
 * Ruta: /admin/proctoring-session-detail (el ID viene del store.proctoringSessionId)
 * Roles: tutor (acotado a su comisión, solo lectura de decisión) | coordinador | admin_sistema
 *
 * L2.5 OBLIGATORIO: muestra disclaimer inamovible en banner superior.
 * Ley 25.326: screenshot_base64 NO se loguea en consola ni se persiste en localStorage.
 * Cliente = sensor no confiable: face_count_servidor y veredicto_reinferencia del servidor
 * son la fuente de verdad (se muestran siempre junto a los datos del cliente).
 *
 * NO HAY VIDEO (RN-CC-01 / RN-CO-03): el expediente es evidencia DISCRETA revisable
 * —screenshots puntuales + eventos + chat + anotaciones + biometría—, nunca una
 * grabación continua. El nombre viejo "Sesiones grabadas" era engañoso; ver el
 * guardrail en `proctoring/expediente.guardrail.test.ts`.
 */

import { useEffect, useMemo, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Icon, Card, SectionTitle, Button } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { ConfirmModal } from '../ui/ConfirmModal';
import { STAFF_NAV } from '../ui/nav';
import { useToast } from '../ui/toast';
import { useNavigate, useRouteParam } from '../lib/router';
import { useApp } from '../lib/store';
import { useAuth } from '../lib/authStore';
import { api } from '../lib/api';
import type { DecisionRevisor, SesionProctoringDetalle } from '../lib/types';
import { tieneCapacidad } from '../lib/capabilities';
import { loadEffectiveConfig, getEffectiveConfig } from '../config/effectiveConfigCache';
import { DetalleHeader } from './proctoring/DetalleHeader';
import { DecisionRevisorForm } from './proctoring/DecisionRevisorForm';
import { EventoCard } from './proctoring/EventoCard';
import { BiometriaCard } from './proctoring/BiometriaCard';
import { RiesgoBanner } from './proctoring/RiesgoBanner';
import { scoreSoftBorder } from './proctoring/helpers';
import { ChatBox } from '../ui/ChatBox';
import { ObservacionesTutor } from './proctoring/ObservacionesTutor';
import { PausaSesionPanel } from './proctoring/PausaSesionPanel';
import { PausasHistorial } from './proctoring/PausasHistorial';

/** Ruta de esta misma pantalla: se re-navega a ella al pasar de caso en la cola. */
const RUTA_PROPIA = '/admin/proctoring-session-detail';

/** Texto del "Volver" según la ruta de origen guardada en el store. */
const BACK_LABELS: Record<string, string> = {
  '/proctor': 'Volver a supervisión en vivo',
  '/proctor/examen': 'Volver al examen',
  '/admin/proctoring-sessions': 'Volver a Registro de sesiones',
  '/admin/cola-revision': 'Volver a la cola de revisión',
};

function VolverLink({ onClick, label }: { onClick: () => void; label: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-base text-label-md text-on-surface-variant hover:text-on-surface transition-colors"
    >
      <Icon name="arrow_back" className="text-[18px]" />
      {label}
    </button>
  );
}

export default function ProctoringSessionDetail() {
  const navigate = useNavigate();
  const toast = useToast();
  const sessionIdFromUrl = useRouteParam('id');
  const sessionIdFromStore = useApp((s) => s.proctoringSessionId);
  const sessionId = sessionIdFromUrl ?? sessionIdFromStore;
  const setProctoringSessionId = useApp((s) => s.setProctoringSessionId);
  const rol = useAuth((s) => s.principal?.roles[0] ?? null);
  const rolesPrincipal = useAuth((s) => s.principal?.roles);
  // Identidad del tutor → se registra como tutor_actor al resolver una pausa.
  const tutorActor = useAuth((s) => s.principal?.email ?? null);
  // C-15: el tutor puede abrir el detalle para chatear/supervisar, pero NO
  // borrar evidencia (regla dura #6: cadena de custodia). El borrado y la lista
  // admin quedan reservados a admin_sistema; el tutor vuelve a su panel.
  const esAdmin = rol === 'admin_sistema';
  // "Volver" regresa al ORIGEN real (supervisión en vivo, grid de personas, cola
  // o grabadas), guardado en el store al abrir el detalle. Fallback por rol si no
  // se seteó (deep-link directo).
  const detailBackRoute = useApp((s) => s.proctoringDetailBackRoute);
  const backRoute = detailBackRoute ?? (esAdmin ? '/admin/proctoring-sessions' : '/proctor');
  const backLabel = BACK_LABELS[backRoute] ?? 'Volver';
  // Cola de casos del examen que se está revisando (la deja Revisor.tsx al abrir
  // un caso). Permite pasar al siguiente SIN volver a la lista: con 20 personas
  // en riesgo, obligar a volver después de cada una convierte la revisión en un
  // trámite de clicks. Vacío = se entró por otro camino (no hay cola que recorrer).
  const cola = useMemo<string[]>(() => {
    try {
      const raw = sessionStorage.getItem('revisor:cola');
      const parsed = raw ? JSON.parse(raw) : null;
      return Array.isArray(parsed?.ids) ? parsed.ids : [];
    } catch {
      return [];
    }
  }, []);
  const indiceEnCola = sessionId ? cola.indexOf(sessionId) : -1;
  const hayCola = indiceEnCola >= 0 && cola.length > 1;

  /** Abre otro caso de la misma cola sin pasar por la lista. */
  const irACaso = (indice: number) => {
    const id = cola[indice];
    if (!id) return;
    setProctoringSessionId(id);
    // El efecto de carga depende de `sessionId`: cambiarlo alcanza para recargar
    // el detalle sin salir de la pantalla.
    navigate(RUTA_PROPIA + '/' + id);
  };

  const [detalle, setDetalle] = useState<SesionProctoringDetalle | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [confirmando, setConfirmando] = useState(false);
  // C-15 (3.3): cierre forzado por el tutor/coordinador (operativo, NO disciplinario).
  const [cerrando, setCerrando] = useState(false);
  const [motivoCierre, setMotivoCierre] = useState('');
  const [cerrada, setCerrada] = useState(false);

  // C-69 admin-sync: el admin puede desactivar el chat y/o las pausas desde la
  // Configuración del sistema. Default `true` (degradación segura): si la config
  // efectiva aún no cargó, NO ocultamos los paneles.
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

  useEffect(() => {
    if (!sessionId) {
      setError('No hay sesión seleccionada.');
      setCargando(false);
      return;
    }
    setCargando(true);
    setError(null);
    api
      .getSesionProctoring(sessionId)
      .then((data) => {
        setDetalle(data);
        // C-15 (3.3): si la sesión ya fue cerrada de forma forzada, reflejarlo al
        // recargar (el botón queda deshabilitado, no se reabre).
        setCerrada(Boolean(data.cierre_forzado_en));
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Error al cargar.'))
      .finally(() => setCargando(false));
  }, [sessionId]);

  const handleConfirmarBorrado = async () => {
    if (!sessionId) return;
    setConfirmando(false);
    const { ok } = await api.eliminarSesionProctoring(sessionId);
    if (ok) {
      toast.success('Sesión eliminada');
      navigate(backRoute);
    } else {
      toast.error('No se pudo eliminar la sesión');
    }
  };

  const handleConfirmarCierre = async () => {
    if (!sessionId) return;
    const motivo = motivoCierre.trim();
    if (!motivo) {
      toast.error('El motivo del cierre es obligatorio');
      return;
    }
    setCerrando(false);
    try {
      await api.cerrarSesionForzado(sessionId, motivo);
      setCerrada(true);
      setMotivoCierre('');
      toast.success('Sesión cerrada de forma forzada');
    } catch {
      toast.error('No se pudo cerrar la sesión');
    }
  };

  // Sesión EN VIVO (supervisión activa) vs GRABADA (finalizada → evidencia de solo
  // lectura). En vivo: chat/observaciones/pausa accionables. Grabada: historial.
  const esVivo = Boolean(detalle && !detalle.finalizada_en) && !cerrada;

  // Solo se decide viniendo de la cola de revisión. Desde "Registro de sesiones"
  // o supervisión en vivo esta pantalla es consulta: meter ahí los botones de
  // anular invitaría a decidir fuera del circuito.
  const vieneDeLaCola = backRoute === '/admin/cola-revision';
  const puedeResolver = tieneCapacidad(rolesPrincipal ?? [], 'revisar_sesion');

  /** Registra la decisión contra el backend, en UN SOLO PASO. `true` solo si el
   * backend confirmó. */
  const registrarDecision = async (
    decision: DecisionRevisor,
    motivo: string,
    evidenciaIds?: string[],
  ): Promise<boolean> => {
    if (!sessionId) return false;
    if (decision !== 'aprobado' && decision !== 'anulado') {
      // 'pendiente' es el estado PREVIO a decidir, no una decisión registrable.
      return false;
    }
    try {
      await api.decidirSesion(sessionId, decision, motivo, evidenciaIds ?? []);
      return true;
    } catch (e) {
      const status = (e as { status?: number })?.status;
      if (status === 409) {
        toast.error('Esta sesión ya tenía una decisión registrada (es inmutable).');
      } else if (status === 403) {
        toast.error('No tenés la atribución para registrar esta decisión.');
      } else {
        toast.error('No se pudo registrar la decisión. Reintentá en un momento.');
      }
      return false;
    }
  };

  /** Tras decidir: pasa al caso siguiente; si era el último, vuelve a la cola. */
  const siguienteCasoOVolver = () => {
    toast.success('Decisión registrada. El score prioriza; la decisión es tuya.');
    if (hayCola && indiceEnCola < cola.length - 1) {
      irACaso(indiceEnCola + 1);
    } else {
      navigate(backRoute);
    }
  };

  return (
    <StaffShell
      nav={STAFF_NAV}
      title="Detalle de sesión"
      help={
        <HelpButton title="Detalle de sesión">
          <p>
            Esta vista concentra toda la <strong>evidencia</strong> de una sesión de proctoring:
            metadata, stat cards (score, eventos, discrepancias), eventos individuales con
            screenshot y veredicto de re-inferencia server-side, y el resultado biométrico.
          </p>
          <p>
            El <em>score</em> prioriza la revisión humana — no es un veredicto. La discrepancia
            marca eventos donde el conteo del cliente no coincide con la re-inferencia del
            backend (el cliente es un sensor no confiable).
          </p>
          <p>
            El screenshot es <strong>dato sensible</strong> (Ley 25.326): finalidad acotada a
            revisión humana, nunca se loguea ni se persiste en el cliente.
          </p>
        </HelpButton>
      }
      actions={
        sessionId && !error ? (
          <div className="flex items-center gap-base">
            {/* C-15 (3.3): cierre forzado — solo si la sesión sigue EN VIVO. En una
                sesión ya finalizada (grabada) no tiene sentido cerrarla. */}
            {esVivo && (
              <Button
                variant="outline"
                size="sm"
                icon="lock"
                onClick={() => setCerrando(true)}
              >
                Cerrar (forzado)
              </Button>
            )}
            {/* Eliminar evidencia — solo admin (cadena de custodia, regla dura #6). */}
            {esAdmin && (
              <Button variant="danger" size="sm" icon="delete" onClick={() => setConfirmando(true)}>
                Eliminar sesión
              </Button>
            )}
          </div>
        ) : undefined
      }
    >
      <div className="space-y-lg animate-in fade-in duration-500">
        {/* Volver a la lista + recorrido de la cola */}
        <div className="flex items-center justify-between gap-md flex-wrap">
          <VolverLink onClick={() => navigate(backRoute)} label={backLabel} />

          {/* Con varios casos en riesgo, pasar al siguiente sin volver a la lista.
              Es la diferencia entre revisar 20 personas y clickear 60 veces. */}
          {hayCola && (
            <div className="flex items-center gap-sm">
              <span className="text-label-sm text-on-surface-variant tabular-nums">
                Caso {indiceEnCola + 1} de {cola.length}
              </span>
              <Button
                variant="outline"
                size="sm"
                icon="chevron_left"
                disabled={indiceEnCola <= 0}
                onClick={() => irACaso(indiceEnCola - 1)}
              >
                Anterior
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={indiceEnCola >= cola.length - 1}
                onClick={() => irACaso(indiceEnCola + 1)}
              >
                Siguiente
                <Icon name="chevron_right" className="text-[16px]" />
              </Button>
            </div>
          )}
        </div>

        {/* Estado de carga */}
        {cargando && (
          <Card className="flex flex-col items-center py-xl gap-sm text-on-surface-variant">
            <Icon name="progress_activity" className="text-[36px] text-on-surface-variant ae-spin" />
            <p className="text-label-md">Cargando sesión…</p>
          </Card>
        )}

        {/* Estado de error */}
        {!cargando && error && (
          <Card className="flex flex-col items-center py-xl gap-sm">
            <Icon name="error" className="text-[40px] text-error" fill />
            <p className="text-title-lg text-on-surface">No se pudo cargar la sesión</p>
            <p className="text-body-md text-on-surface-variant">{error}</p>
            <div className="pt-sm">
              <Button variant="outline" size="sm" icon="arrow_back" onClick={() => navigate(backRoute)}>
                Volver
              </Button>
            </div>
          </Card>
        )}

        {/* Contenido */}
        {!cargando && !error && detalle && (
          <>
            <DetalleHeader detalle={detalle} />

            {/* C-76 bloque 9.1: estado visual con/sin riesgo, siempre visible — no
                solo en la cola de revisión — para que cualquiera que abra el detalle
                (tutor incluido) entienda de un vistazo si esta sesión pide atención. */}
            <RiesgoBanner score={detalle.score} />

            {/* Decisión del revisor, JUNTO al expediente. Solo cuando se entró
                desde la cola (`backRoute`) y la sesión está cerrada: no se decide
                sobre un examen en curso, ni desde el registro histórico. */}
            {vieneDeLaCola && !esVivo && (
              <Card>
                <DecisionRevisorForm
                  puedeResolver={puedeResolver}
                  eventos={detalle.eventos}
                  onResolver={registrarDecision}
                  onDecidido={siguienteCasoOVolver}
                />
              </Card>
            )}

            {/* Pausa: EN VIVO el tutor/coordinador la resuelve acá; GRABADA muestra el
                historial de todas las pausas como evidencia (solo lectura).
                C-69 admin-sync: si el admin desactivó las pausas, se oculta la gestión. */}
            {sessionId && pausasHabilitadas && (
              esVivo
                ? <PausaSesionPanel sessionId={sessionId} tutorActor={tutorActor} />
                : <PausasHistorial sessionId={sessionId} />
            )}

            {/* Biometría — arriba del contenido para verla junto al header */}
            <BiometriaCard biometria={detalle.biometria} />

            {/* Eventos (izquierda) + chat del tutor (derecha) en dos columnas.
                En mobile colapsan a una sola columna (eventos arriba, chat abajo). */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-lg items-start">
              {/* Eventos registrados — columna izquierda. Borde tintado por riesgo
                  (C-76 bloque 9.1): mismo lenguaje visual que las listas (SesionCard). */}
              <Card className={`space-y-md ${scoreSoftBorder(detalle.score)}`}>
                <SectionTitle
                  sub={`${detalle.eventos.length} evento${detalle.eventos.length !== 1 ? 's' : ''} registrado${
                    detalle.eventos.length !== 1 ? 's' : ''
                  }`}
                >
                  Eventos de la sesión
                </SectionTitle>

                {detalle.eventos.length === 0 ? (
                  <div className="flex flex-col items-center text-center py-xl gap-sm text-on-surface-variant">
                    <Icon name="check_circle" className="text-success text-[36px]" fill />
                    <p className="text-body-md">Sin eventos registrados en esta sesión.</p>
                  </div>
                ) : (
                  <div className="space-y-sm">
                    {detalle.eventos.map((ev) => (
                      <EventoCard key={ev.evento_id} evento={ev} />
                    ))}
                  </div>
                )}
              </Card>

              {/* C-15: canal de chat con el alumno + observaciones del tutor.
                  Sticky en desktop para que acompañe el scroll de la lista de eventos. */}
              <div className="lg:sticky lg:top-lg space-y-lg">
                {/* C-69 admin-sync: el chat se oculta si el admin lo desactivó. */}
                {chatHabilitado && (
                  <ChatBox
                    sessionId={sessionId}
                    yo="tutor"
                    titulo={esVivo ? 'Canal con el estudiante' : 'Historial del canal con el estudiante'}
                    altura="h-[420px]"
                    readOnly={!esVivo}
                  />
                )}
                {/* C-15 (3.2): observaciones del tutor — insumo de la revisión C-16.
                    En grabada se muestran como evidencia (solo lectura). */}
                <ObservacionesTutor sessionId={sessionId} tutorActor={tutorActor} readOnly={!esVivo} />
              </div>
            </div>
          </>
        )}
      </div>

      <ConfirmModal
        abierto={confirmando}
        variante="danger"
        titulo="Eliminar sesión grabada"
        mensaje={
          <>
            Vas a eliminar{' '}
            <strong className="text-on-surface">
              {detalle?.etiqueta?.trim() || 'esta sesión'}
            </strong>
            . Esta acción no se puede deshacer.
          </>
        }
        textoConfirmar="Eliminar"
        textoCancelar="Cancelar"
        onConfirmar={() => void handleConfirmarBorrado()}
        onCancelar={() => setConfirmando(false)}
      />

      {/* C-15 (3.3): cierre forzado — pide motivo OBLIGATORIO. Operativo, NO
          disciplinario (L2.5: el veredicto es humano en C-16). */}
      <ConfirmModal
        abierto={cerrando}
        variante="default"
        titulo="Cerrar sesión (forzado)"
        mensaje={
          <div className="space-y-sm text-left">
            <p>
              Vas a cerrar de forma forzada{' '}
              <strong className="text-on-surface">
                {detalle?.etiqueta?.trim() || 'esta sesión'}
              </strong>
              . Es una acción <strong>operativa</strong>, no un veredicto disciplinario.
              Quedará registrada con tu autoría y el motivo.
            </p>
            <textarea
              value={motivoCierre}
              onChange={(e) => setMotivoCierre(e.target.value)}
              rows={3}
              placeholder="Motivo del cierre (obligatorio)…"
              className="w-full px-sm py-base text-label-md rounded-xl border border-outline-variant bg-surface-container-lowest focus:border-primary-container outline-none resize-none"
            />
          </div>
        }
        textoConfirmar="Cerrar sesión"
        textoCancelar="Cancelar"
        onConfirmar={() => void handleConfirmarCierre()}
        onCancelar={() => {
          setCerrando(false);
          setMotivoCierre('');
        }}
      />
    </StaffShell>
  );
}
