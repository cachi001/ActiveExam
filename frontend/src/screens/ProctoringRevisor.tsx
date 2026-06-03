/**
 * ProctoringRevisor — Lista de sesiones grabadas del backend slim C-45 (C-46).
 *
 * Ruta: /admin/proctoring-sessions (roles: admin_examenes | coordinador | revisor)
 * Accede a GET /proctoring/sessions via api.listarSesionesProctoring() (dual real/mock).
 *
 * L2.5: este módulo NO sanciona automáticamente. El score es un indicador de
 * prioridad para revisión humana. La decisión disciplinaria es siempre del revisor.
 * Ley 25.326: no se persiste screenshot_base64 en este componente (solo se lista).
 */

import { useEffect, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Icon, Card, Badge, SectionTitle, Button } from '../ui/components';
import { STAFF_NAV } from '../ui/nav';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api } from '../lib/api';
import type { SesionProctoringResumen } from '../lib/types';

/** ID de la sesión seleccionada para navegar al detalle (via store). */
const PROCTORING_DETAIL_ROUTE = '/admin/proctoring-session-detail';

function formatFecha(iso: string): string {
  try {
    return new Date(iso).toLocaleString('es-AR', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function scoreColor(score: number): string {
  if (score >= 60) return 'text-error';
  if (score >= 30) return 'text-warning';
  return 'text-success';
}

function modoBadgeTone(modo: string): 'primary' | 'neutral' | 'warning' {
  if (modo === 'examen') return 'primary';
  if (modo === 'diagnostico') return 'warning';
  return 'neutral';
}

export default function ProctoringRevisor() {
  const navigate = useNavigate();
  const setProctoringSessionId = useApp((s) => s.setProctoringSessionId);
  const [sesiones, setSesiones] = useState<SesionProctoringResumen[]>([]);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    setCargando(true);
    api.listarSesionesProctoring()
      .then((data) => { setSesiones(data); })
      .catch(() => { setSesiones([]); })
      .finally(() => { setCargando(false); });
  }, []);

  const handleSeleccionar = (sesion: SesionProctoringResumen) => {
    // Guardar el ID en el store para que ProctoringSessionDetail lo lea
    setProctoringSessionId(sesion.id);
    navigate(PROCTORING_DETAIL_ROUTE);
  };

  const handleEliminar = async (sesion: SesionProctoringResumen) => {
    // eslint-disable-next-line no-alert -- herramienta admin: confirm directo es aceptable
    if (!window.confirm('¿Eliminar esta sesión grabada? Esta acción no se puede deshacer.')) return;
    const { ok } = await api.eliminarSesionProctoring(sesion.id);
    if (ok) {
      // Quitar la sesión eliminada del estado local sin recargar todo
      setSesiones((prev) => prev.filter((s) => s.id !== sesion.id));
    }
    // Si ok=false: dejamos la lista como está (degradación silenciosa).
  };

  return (
    <StaffShell nav={STAFF_NAV} title="Sesiones grabadas">
      <div className="space-y-lg animate-in fade-in duration-300">

        {/* Header */}
        <div className="flex items-center justify-between gap-md flex-wrap">
          <div>
            <h1 className="font-headline text-headline-md text-on-surface">Sesiones de proctoring</h1>
            <p className="text-body-sm text-on-surface-variant mt-base">
              Historial de sesiones grabadas desde el harness diagnóstico y exámenes reales.
            </p>
          </div>
          <div className="flex items-center gap-base p-sm rounded-lg bg-primary-fixed/40 border border-primary/20 text-label-sm text-on-primary-fixed-variant">
            <Icon name="shield" className="text-[16px] shrink-0" fill />
            <span>Decisión humana</span>
          </div>
        </div>

        {/* Lista */}
        <Card className="space-y-md">
          <SectionTitle sub={cargando ? 'Cargando…' : `${sesiones.length} sesión${sesiones.length !== 1 ? 'es' : ''}`}>
            Sesiones grabadas
          </SectionTitle>

          {cargando && (
            <div className="flex flex-col items-center py-xl gap-sm text-on-surface-variant">
              <Icon name="progress_activity" className="text-[36px] text-primary animate-spin" />
              <p className="text-label-sm">Cargando sesiones…</p>
            </div>
          )}

          {!cargando && sesiones.length === 0 && (
            <div className="flex flex-col items-center py-xl gap-sm text-on-surface-variant">
              <Icon name="video_library" className="text-[40px]" />
              <p className="text-label-md">No hay sesiones grabadas aún.</p>
              <p className="text-label-sm text-center max-w-xs">
                Iniciá el harness de diagnóstico y presioná "Grabar sesión" para registrar eventos en el backend slim.
              </p>
            </div>
          )}

          {!cargando && sesiones.length > 0 && (
            <div className="space-y-sm">
              {sesiones.map((s) => (
                <div
                  key={s.id}
                  className="relative rounded-xl border border-outline-variant/40 bg-surface-container-low hover:bg-surface-container hover:border-primary/30 transition-all group"
                >
                  <button
                    type="button"
                    onClick={() => handleSeleccionar(s)}
                    className="w-full text-left p-md pr-12 space-y-sm rounded-xl"
                  >
                    {/* Fila 1: ID + modo + etiqueta */}
                    <div className="flex items-center gap-sm flex-wrap">
                      <span className="font-mono text-label-sm text-on-surface-variant">
                        {s.id.slice(0, 20)}…
                      </span>
                      <Badge tone={modoBadgeTone(s.modo)}>
                        {s.modo}
                      </Badge>
                      {s.etiqueta && (
                        <span className="text-label-sm text-on-surface font-semibold">{s.etiqueta}</span>
                      )}
                    </div>

                    {/* Fila 2: métricas */}
                    <div className="flex items-center gap-md flex-wrap text-label-sm">
                      <span className="text-on-surface-variant">
                        <Icon name="calendar_today" className="text-[14px] inline mr-base" />
                        {formatFecha(s.creada_en)}
                      </span>
                      <span className="text-on-surface">
                        <Icon name="notifications" className="text-[14px] inline mr-base" />
                        {s.total_eventos} eventos
                      </span>
                      {s.total_discrepancias > 0 && (
                        <span className="text-error font-semibold">
                          <Icon name="warning" className="text-[14px] inline mr-base" fill />
                          {s.total_discrepancias} discrepancias
                        </span>
                      )}
                      <span className={`font-bold ${scoreColor(s.score)}`}>
                        Score: {s.score}
                      </span>
                    </div>

                    {/* Flecha */}
                    <div className="flex justify-end">
                      <Icon name="arrow_forward" className="text-[18px] text-primary opacity-0 group-hover:opacity-100 transition-opacity" />
                    </div>
                  </button>

                  {/* Eliminar sesión (no dispara la navegación al detalle) */}
                  <Button
                    variant="ghost"
                    size="sm"
                    icon="delete"
                    aria-label="Eliminar sesión"
                    title="Eliminar sesión"
                    onClick={(e) => {
                      e.stopPropagation();
                      void handleEliminar(s);
                    }}
                    className="absolute top-sm right-sm text-on-surface-variant hover:text-error"
                  />
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </StaffShell>
  );
}
