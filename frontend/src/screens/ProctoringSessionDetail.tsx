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

const LISTA_ROUTE = '/admin/proctoring-sessions';

function VolverLink({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-base text-label-md text-primary hover:underline"
    >
      <Icon name="arrow_back" className="text-[18px]" />
      Volver a la lista de sesiones
    </button>
  );
}

export default function ProctoringSessionDetail() {
  const navigate = useNavigate();
  const toast = useToast();
  const sessionId = useApp((s) => s.proctoringSessionId);
  const [detalle, setDetalle] = useState<SesionProctoringDetalle | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [confirmando, setConfirmando] = useState(false);

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
      .then((data) => setDetalle(data))
      .catch((e) => setError(e instanceof Error ? e.message : 'Error al cargar.'))
      .finally(() => setCargando(false));
  }, [sessionId]);

  const handleConfirmarBorrado = async () => {
    if (!sessionId) return;
    setConfirmando(false);
    const { ok } = await api.eliminarSesionProctoring(sessionId);
    if (ok) {
      toast.success('Sesión eliminada');
      navigate(LISTA_ROUTE);
    } else {
      toast.error('No se pudo eliminar la sesión');
    }
  };

  return (
    <StaffShell nav={STAFF_NAV} title="Detalle de sesión">
      <div className="space-y-lg animate-in fade-in duration-500">
        {/* Disclaimer L2.5 — inamovible */}
        <div
          role="note"
          className="flex items-start gap-sm p-md rounded-xl bg-primary-fixed/50
            border border-primary/20 text-label-sm text-on-primary-fixed-variant"
        >
          <Icon name="shield" className="text-[20px] shrink-0 mt-px" fill />
          <div>
            <p className="font-bold">Revisión humana obligatoria</p>
            <p className="mt-base">
              Este sistema <strong>nunca sanciona automáticamente</strong>. El score es un indicador
              de prioridad para revisión humana. La decisión disciplinaria es{' '}
              <strong>siempre del revisor</strong>. Los screenshots son dato sensible (Ley 25.326):
              finalidad acotada a revisión humana.
            </p>
          </div>
        </div>

        {/* Acciones: volver + eliminar */}
        <div className="flex items-center justify-between gap-md flex-wrap">
          <VolverLink onClick={() => navigate(LISTA_ROUTE)} />
          {sessionId && !error && (
            <Button variant="danger" size="sm" icon="delete" onClick={() => setConfirmando(true)}>
              Eliminar sesión
            </Button>
          )}
        </div>

        {/* Estado de carga */}
        {cargando && (
          <Card className="flex flex-col items-center py-xl gap-sm text-on-surface-variant">
            <Icon name="progress_activity" className="text-[36px] text-primary ae-spin" />
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
              <Button variant="outline" size="sm" icon="arrow_back" onClick={() => navigate(LISTA_ROUTE)}>
                Volver a la lista
              </Button>
            </div>
          </Card>
        )}

        {/* Contenido */}
        {!cargando && !error && detalle && (
          <>
            <DetalleHeader detalle={detalle} />

            {/* Eventos */}
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

            {/* Biometría */}
            <BiometriaCard biometria={detalle.biometria} />

            {/* Volver (pie) */}
            <VolverLink onClick={() => navigate(LISTA_ROUTE)} />
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
    </StaffShell>
  );
}
