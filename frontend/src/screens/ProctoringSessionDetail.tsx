/**
 * ProctoringSessionDetail — Detalle completo de una sesión de proctoring (C-46).
 *
 * Ruta: /admin/proctoring-session-detail (el ID viene del store.proctoringSessionId)
 * Roles: admin_examenes | coordinador | revisor
 *
 * L2.5 OBLIGATORIO: muestra disclaimer inamovible en banner superior.
 * Ley 25.326: screenshot_base64 NO se loguea en consola ni se persiste en localStorage.
 * Cliente = sensor no confiable: face_count_servidor y veredicto_reinferencia del servidor
 * son la fuente de verdad (se muestran siempre junto a los datos del cliente).
 */

import { useEffect, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Icon, Card, SectionTitle, Button } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { ConfirmModal } from '../ui/ConfirmModal';
import { STAFF_NAV } from '../ui/nav';
import { useToast } from '../ui/toast';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api } from '../lib/api';
import type { SesionProctoringDetalle } from '../lib/types';
import { DetalleHeader } from './proctoring/DetalleHeader';
import { EventoCard } from './proctoring/EventoCard';
import { BiometriaCard } from './proctoring/BiometriaCard';
import { ChatBox } from '../ui/ChatBox';
import { ObservacionesProctor } from './proctoring/ObservacionesProctor';

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
  const sessionId = useApp((s) => s.proctoringSessionId);
  const rol = useApp((s) => s.rol);
  // C-15: el proctor puede abrir el detalle para chatear/supervisar, pero NO
  // borrar evidencia (regla dura #6: cadena de custodia). El borrado y la lista
  // admin quedan reservados a admin_sistema; el proctor vuelve a su panel.
  const esAdmin = rol === 'admin_sistema';
  const backRoute = esAdmin ? '/admin/proctoring-sessions' : '/proctor';
  const [detalle, setDetalle] = useState<SesionProctoringDetalle | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [confirmando, setConfirmando] = useState(false);
  // C-15 (3.3): cierre forzado por el proctor (operativo, NO disciplinario).
  const [cerrando, setCerrando] = useState(false);
  const [motivoCierre, setMotivoCierre] = useState('');
  const [cerrada, setCerrada] = useState(false);

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
            {/* C-15 (3.3): cierre forzado — proctor y admin. Operativo, NO disciplinario. */}
            <Button
              variant="outline"
              size="sm"
              icon="lock"
              onClick={() => setCerrando(true)}
              disabled={cerrada}
            >
              {cerrada ? 'Sesión cerrada' : 'Cerrar (forzado)'}
            </Button>
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
        {/* Volver a la lista */}
        <VolverLink
          onClick={() => navigate(backRoute)}
          label={esAdmin ? 'Volver a la lista de sesiones' : 'Volver al panel'}
        />

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

            {/* Eventos (izquierda) + chat del proctor (derecha) en dos columnas.
                En mobile colapsan a una sola columna (eventos arriba, chat abajo). */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-lg items-start">
              {/* Eventos registrados — columna izquierda */}
              <Card className="space-y-md">
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

              {/* C-15: canal de chat con el alumno + observaciones del proctor.
                  Sticky en desktop para que acompañe el scroll de la lista de eventos. */}
              <div className="lg:sticky lg:top-lg space-y-lg">
                <ChatBox
                  sessionId={sessionId}
                  yo="proctor"
                  titulo="Canal con el estudiante"
                  altura="h-[420px]"
                />
                {/* C-15 (3.2): observaciones del proctor — insumo de la revisión C-16. */}
                <ObservacionesProctor sessionId={sessionId} />
              </div>
            </div>

            {/* Biometría */}
            <BiometriaCard biometria={detalle.biometria} />
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
