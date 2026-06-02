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
import { Icon, Card, Badge, SeverityBadge, SectionTitle } from '../ui/components';
import { STAFF_NAV } from '../ui/nav';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api, TIPO_EVENTO_LABEL } from '../lib/api';
import type { SesionProctoringDetalle, EventoProctoringDetalle, VeredictoReinferencia } from '../lib/types';
import type { Severidad, TipoEvento } from '../lib/types';

// ---------------------------------------------------------------------------
// Helpers de presentación
// ---------------------------------------------------------------------------

function formatFecha(iso: string): string {
  try {
    return new Date(iso).toLocaleString('es-AR', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  } catch {
    return iso;
  }
}

/** Clases Tailwind para el gauge de score (misma lógica que AdminDetectionHarness). */
function gaugeColor(score: number, threshold = 60): string {
  if (score >= threshold) return 'bg-error';
  if (score >= threshold * 0.7) return 'bg-warning';
  return 'bg-success';
}

function gaugeTextColor(score: number, threshold = 60): string {
  if (score >= threshold) return 'text-error';
  if (score >= threshold * 0.7) return 'text-warning';
  return 'text-success';
}

/** Clases semánticas para veredicto de re-inferencia (spec 9.7). */
function verdictClasses(v: VeredictoReinferencia | null | undefined): string {
  if (v === 'coincide') return 'bg-success-container text-success border-success/30';
  if (v === 'discrepancia') return 'bg-error-container text-on-error-container border-error/30';
  return 'bg-surface-container text-on-surface-variant border-outline-variant/40';
}

function verdictLabel(v: VeredictoReinferencia | null | undefined): string {
  if (!v) return '—';
  const map: Record<VeredictoReinferencia, string> = {
    coincide: 'Coincide',
    discrepancia: 'Discrepancia',
    sin_referencia: 'Sin referencia',
    error: 'Error',
  };
  return map[v] ?? v;
}

// ---------------------------------------------------------------------------
// Sub-componente: miniatura de screenshot expandible
// ---------------------------------------------------------------------------

function ScreenshotMiniatura({ base64 }: { base64: string | null | undefined }) {
  const [expanded, setExpanded] = useState(false);

  if (!base64) {
    return (
      <span className="text-label-sm text-on-surface-variant italic">Sin captura</span>
    );
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setExpanded(true)}
        className="block rounded overflow-hidden border border-outline-variant/40 hover:border-primary/40 transition-colors"
        title="Click para expandir"
      >
        {/* DATO SENSIBLE (Ley 25.326): NO log en consola — renderizado directo */}
        <img
          src={base64}
          alt="Captura del evento"
          style={{ maxHeight: 120, display: 'block' }}
          className="object-contain bg-inverse-surface"
        />
      </button>

      {/* Overlay modal ligero */}
      {expanded && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Screenshot del evento"
          className="fixed inset-0 z-[200] bg-black/70 flex items-center justify-center p-md"
          onClick={() => setExpanded(false)}
        >
          <div className="relative max-w-3xl w-full" onClick={(e) => e.stopPropagation()}>
            <img
              src={base64}
              alt="Captura expandida del evento"
              className="w-full rounded-xl border border-outline-variant/40"
            />
            <button
              type="button"
              onClick={() => setExpanded(false)}
              className="absolute top-sm right-sm bg-surface rounded-full p-base shadow-md"
              aria-label="Cerrar"
            >
              <Icon name="close" className="text-[20px]" />
            </button>
          </div>
        </div>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Componente principal
// ---------------------------------------------------------------------------

export default function ProctoringSessionDetail() {
  const navigate = useNavigate();
  const sessionId = useApp((s) => s.proctoringSessionId);
  const [detalle, setDetalle] = useState<SesionProctoringDetalle | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) {
      setError('No hay sesión seleccionada.');
      setCargando(false);
      return;
    }
    setCargando(true);
    setError(null);
    api.getSesionProctoring(sessionId)
      .then((data) => { setDetalle(data); })
      .catch((e) => { setError(e instanceof Error ? e.message : 'Error al cargar.'); })
      .finally(() => { setCargando(false); });
  }, [sessionId]);

  return (
    <StaffShell nav={STAFF_NAV} title="Detalle de sesión">
      <div className="space-y-lg animate-in fade-in duration-300">

        {/* ================================================================
            DISCLAIMER L2.5 — INAMOVIBLE (spec 9.3)
        ================================================================ */}
        <div
          role="note"
          className="flex items-start gap-sm p-md rounded-xl bg-primary-fixed/40 border border-primary/20 text-label-sm text-on-primary-fixed-variant"
        >
          <Icon name="shield" className="text-[20px] shrink-0 mt-px" fill />
          <div>
            <p className="font-bold">Sistema L2.5 — Revisión humana obligatoria</p>
            <p className="mt-base">
              Este sistema <strong>nunca sanciona automáticamente</strong>.
              El score es un indicador de prioridad para revisión humana.
              La decisión disciplinaria es <strong>siempre del revisor</strong>.
              Los screenshots son dato sensible (Ley 25.326): finalidad acotada a revisión humana.
            </p>
          </div>
        </div>

        {/* Botón volver */}
        <div>
          <button
            type="button"
            onClick={() => navigate('/admin/proctoring-sessions')}
            className="inline-flex items-center gap-sm text-label-sm text-primary hover:underline"
          >
            <Icon name="arrow_back" className="text-[16px]" />
            Volver a la lista de sesiones
          </button>
        </div>

        {/* Estado de carga / error */}
        {cargando && (
          <Card className="flex flex-col items-center py-xl gap-sm text-on-surface-variant">
            <Icon name="progress_activity" className="text-[36px] text-primary animate-spin" />
            <p className="text-label-sm">Cargando sesión…</p>
          </Card>
        )}

        {!cargando && error && (
          <Card className="flex flex-col items-center py-xl gap-sm text-on-surface-variant">
            <Icon name="error" className="text-[36px] text-error" fill />
            <p className="text-label-md text-error">{error}</p>
          </Card>
        )}

        {/* Contenido del detalle */}
        {!cargando && !error && detalle && (
          <>
            {/* ================================================================
                METADATA DE SESIÓN (spec 9.4)
            ================================================================ */}
            <Card className="space-y-md">
              <SectionTitle sub={`ID: ${detalle.id}`}>Información de la sesión</SectionTitle>

              <div className="grid sm:grid-cols-2 gap-md text-label-sm">
                <div>
                  <p className="text-on-surface-variant">Modo</p>
                  <Badge tone={detalle.modo === 'examen' ? 'primary' : 'warning'}>{detalle.modo}</Badge>
                </div>
                {detalle.etiqueta && (
                  <div>
                    <p className="text-on-surface-variant">Etiqueta</p>
                    <p className="font-semibold text-on-surface">{detalle.etiqueta}</p>
                  </div>
                )}
                <div>
                  <p className="text-on-surface-variant">Fecha</p>
                  <p className="text-on-surface">{formatFecha(detalle.creada_en)}</p>
                </div>
                <div>
                  <p className="text-on-surface-variant">Total eventos</p>
                  <p className="text-on-surface">{detalle.total_eventos}</p>
                </div>
                <div>
                  <p className="text-on-surface-variant">Discrepancias</p>
                  <p className={detalle.total_discrepancias > 0 ? 'text-error font-bold' : 'text-on-surface'}>
                    {detalle.total_discrepancias}
                  </p>
                </div>
              </div>

              {/* Gauge de score */}
              <div className="space-y-sm pt-sm border-t border-outline-variant/40">
                <div className="flex items-center justify-between">
                  <span className="text-label-sm text-on-surface-variant">Score acumulado</span>
                  <span className={`font-headline text-headline-sm font-bold ${gaugeTextColor(detalle.score)}`}>
                    {detalle.score}%
                  </span>
                </div>
                <div className="bg-surface-container-high rounded-full h-3 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-300 ${gaugeColor(detalle.score)}`}
                    style={{ width: `${Math.min(100, detalle.score)}%` }}
                    role="progressbar"
                    aria-valuenow={detalle.score}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label="Score de riesgo"
                  />
                </div>
                <p className="text-[11px] text-on-surface-variant">
                  Score acumulativo de priorización — NO determina sanción (L2.5).
                </p>
              </div>
            </Card>

            {/* ================================================================
                LISTA DE EVENTOS (spec 9.5–9.8)
            ================================================================ */}
            <Card className="space-y-md">
              <SectionTitle sub={`${detalle.eventos.length} evento${detalle.eventos.length !== 1 ? 's' : ''} registrados`}>
                Eventos de la sesión
              </SectionTitle>

              {detalle.eventos.length === 0 && (
                <div className="text-center py-xl text-on-surface-variant space-y-sm">
                  <Icon name="check_circle" className="text-success text-[36px]" fill />
                  <p className="text-label-sm">Sin eventos registrados en esta sesión.</p>
                </div>
              )}

              <div className="space-y-sm">
                {detalle.eventos.map((ev: EventoProctoringDetalle) => {
                  const tipoLabel = TIPO_EVENTO_LABEL[ev.tipo as TipoEvento] ?? ev.tipo;
                  const fcCliente = ev.face_count_cliente ?? null;
                  const fcServidor = ev.face_count_servidor ?? null;
                  const discrepanciaFC = fcCliente !== null && fcServidor !== null && fcCliente !== fcServidor;

                  return (
                    <div
                      key={ev.evento_id}
                      className={`rounded-xl border p-md space-y-sm ${
                        ev.severidad === 'alta' || ev.severidad === 'critica'
                          ? 'bg-error-container/10 border-error/30'
                          : 'bg-surface-container-low border-outline-variant/40'
                      }`}
                    >
                      {/* Fila 1: tipo + severidad + timestamp */}
                      <div className="flex items-center justify-between gap-sm flex-wrap">
                        <div className="flex items-center gap-sm flex-wrap">
                          <span className="font-semibold text-label-md text-on-surface">{tipoLabel}</span>
                          <SeverityBadge severidad={ev.severidad as Severidad} />
                        </div>
                        <span className="text-label-sm text-on-surface-variant font-mono">
                          {formatFecha(ev.ts_cliente)}
                        </span>
                      </div>

                      {/* Fila 2: veredicto re-inferencia (spec 9.7) */}
                      {ev.veredicto_reinferencia !== undefined && (
                        <div className="flex items-center gap-sm">
                          <span className="text-label-sm text-on-surface-variant">Veredicto servidor:</span>
                          <span className={`inline-flex items-center gap-base px-sm py-px rounded-full text-label-sm font-semibold border ${verdictClasses(ev.veredicto_reinferencia)}`}>
                            {verdictLabel(ev.veredicto_reinferencia)}
                          </span>
                        </div>
                      )}

                      {/* Fila 3: face_count cliente vs servidor (spec 9.8) */}
                      {(fcCliente !== null || fcServidor !== null) && (
                        <div className="flex items-center gap-sm flex-wrap text-label-sm">
                          <span className="text-on-surface-variant">Rostros:</span>
                          <span className="text-on-surface">
                            Cliente: <strong>{fcCliente ?? '—'}</strong>
                            {' · '}
                            Servidor: <strong>{fcServidor ?? '—'}</strong>
                          </span>
                          {discrepanciaFC && (
                            <Badge tone="error">Discrepancia</Badge>
                          )}
                        </div>
                      )}

                      {/* Fila 4: Screenshot (spec 9.6) */}
                      <div>
                        <p className="text-label-sm text-on-surface-variant mb-base">Captura:</p>
                        <ScreenshotMiniatura base64={ev.screenshot_base64} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>

            {/* ================================================================
                SECCIÓN BIOMETRÍA (spec 9.9)
            ================================================================ */}
            <Card className="space-y-md">
              <SectionTitle>Verificación biométrica</SectionTitle>

              {detalle.biometria === null ? (
                <div className="flex items-center gap-sm text-label-sm text-on-surface-variant py-sm">
                  <Icon name="fingerprint" className="text-[20px]" />
                  Sin verificación biométrica registrada en esta sesión.
                </div>
              ) : (
                <div className="space-y-sm text-label-sm">
                  <div className="flex items-center gap-sm">
                    <Icon
                      name={detalle.biometria.liveness_ok ? 'verified' : 'cancel'}
                      className={`text-[20px] ${detalle.biometria.liveness_ok ? 'text-success' : 'text-error'}`}
                      fill
                    />
                    <span className={`font-semibold ${detalle.biometria.liveness_ok ? 'text-success' : 'text-error'}`}>
                      Liveness: {detalle.biometria.liveness_ok ? 'OK' : 'FALLÓ'}
                    </span>
                  </div>

                  <div>
                    <p className="text-on-surface-variant mb-base">Retos resueltos:</p>
                    {detalle.biometria.retos_resueltos.length === 0 ? (
                      <span className="text-on-surface-variant italic">Ninguno registrado</span>
                    ) : (
                      <div className="flex gap-base flex-wrap">
                        {detalle.biometria.retos_resueltos.map((reto) => (
                          <Badge key={reto} tone="neutral">{reto}</Badge>
                        ))}
                      </div>
                    )}
                  </div>

                  <div>
                    <span className="text-on-surface-variant">Resultado: </span>
                    <span className="font-semibold text-on-surface">{detalle.biometria.resultado}</span>
                  </div>
                </div>
              )}
            </Card>

            {/* Botón volver (parte inferior) */}
            <div>
              <button
                type="button"
                onClick={() => navigate('/admin/proctoring-sessions')}
                className="inline-flex items-center gap-sm text-label-sm text-primary hover:underline"
              >
                <Icon name="arrow_back" className="text-[16px]" />
                Volver a la lista de sesiones
              </button>
            </div>
          </>
        )}
      </div>
    </StaffShell>
  );
}
