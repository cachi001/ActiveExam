import { useEffect, useState } from 'react';
import { StudentShell } from '../ui/shells';
import { Icon, Button, Card } from '../ui/components';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api } from '../lib/api';
import { loadEffectiveConfig, getEffectiveConfig, resetEffectiveConfigCache } from '../config/effectiveConfigCache';
import { UMBRAL_REVISION_MIN } from '../config/umbralRevision';
import type { NotaExamen, RevisionExamen } from '../lib/types';

export default function Cierre() {
  const navigate = useNavigate();
  const score = useApp((s) => s.scorePropio);
  const examen = useApp((s) => s.examenActivo);
  const resetSesion = useApp((s) => s.resetSesion);
  const proctoringSessionId = useApp((s) => s.proctoringSessionId);

  const examenId = examen?.examen_contenido_id ?? examen?.id ?? null;

  const [umbralRevision, setUmbralRevision] = useState<number | null>(null);
  const [nota, setNota] = useState<NotaExamen | null>(null);
  const [revision, setRevision] = useState<RevisionExamen | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        resetEffectiveConfigCache();
        await loadEffectiveConfig();
        setUmbralRevision(getEffectiveConfig()?.umbral_cola_revision ?? null);
      } catch { /* sin red: cae al fallback del examen */ }
    })();
  }, []);

  // Finaliza primero; recién después sondea misNotas para evitar race condition
  // (misNotas INNER JOINs moodle_writeback_estado que solo existe tras finalizar).
  useEffect(() => {
    if (!examen) return;
    const objetivoId = examen.examen_contenido_id ?? examen.id;
    let cancelado = false;
    let intentos = 0;
    const buscar = async () => {
      const [notas, rev] = await Promise.all([
        api.misNotas().catch(() => []),
        objetivoId ? api.revisionExamen(objetivoId).catch(() => null) : Promise.resolve(null),
      ]);
      if (cancelado) return;
      const match = notas.find((n) => n.examen_id === objetivoId);
      if (match) setNota(match);
      if (rev) setRevision(rev);
      if ((!match || !rev) && ++intentos < 8) setTimeout(buscar, 1500);
    };
    void (async () => {
      if (proctoringSessionId) {
        await api.finalizarSesionProctoring(proctoringSessionId).catch(() => null);
      }
      if (!cancelado) void buscar();
    })();
    return () => { cancelado = true; };
  }, [examen, proctoringSessionId]);

  const umbralEfectivo = nota?.umbral_revision ?? umbralRevision ?? examen?.umbral_score ?? UMBRAL_REVISION_MIN;
  const irARevision = nota ? nota.en_cola_revision : score >= umbralEfectivo;
  // C-69: la nota puede estar OCULTA hasta el cierre (nota_visible=false → nota=null).
  const notaPendiente = nota != null && nota.nota_visible === false;
  const tieneNota = nota != null && nota.nota !== null && nota.nota !== undefined;
  const resultadosVisibles = revision != null && revision.disponible !== false;
  const puedeRevisar = !!nota?.revision_disponible && resultadosVisibles && (revision?.total_preguntas ?? 0) > 0;
  const notaMax = nota?.nota_maxima ?? revision?.nota_maxima ?? 10;
  const pct = resultadosVisibles && revision && revision.total_preguntas > 0
    ? Math.round((revision.correctas / revision.total_preguntas) * 100)
    : null;

  const fmtFecha = (iso: string | null | undefined) =>
    iso ? new Date(iso).toLocaleString('es-AR', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';

  const volver = () => { resetSesion(); navigate('/login'); };
  const revisar = () => { if (examenId) navigate(`/alumno/revision/${examenId}`); };

  // Filas de la ficha de resultados (con MI información del intento).
  const ficha: Array<{ icono: string; color: string; label: string; valor: string }> = [];
  if (revision && resultadosVisibles) {
    ficha.push({ icono: 'quiz', color: 'text-on-surface-variant', label: 'Preguntas', valor: String(revision.total_preguntas) });
    ficha.push({ icono: 'check_circle', color: 'text-success', label: 'Correctas', valor: String(revision.correctas) });
    ficha.push({ icono: 'cancel', color: 'text-error', label: 'Incorrectas', valor: String(revision.incorrectas) });
    ficha.push({ icono: 'help', color: 'text-warning', label: 'Sin responder', valor: String(revision.sin_responder) });
  }

  return (
    <StudentShell>
      <div className="w-full space-y-lg animate-in fade-in duration-300">
        {/* Encabezado */}
        <div className="flex items-center gap-md">
          <div className="w-12 h-12 rounded-full bg-success-container text-success flex items-center justify-center shrink-0">
            <Icon name="check_circle" className="text-[28px]" fill />
          </div>
          <div>
            <h1 className="font-headline text-headline-md text-on-surface">¡Examen finalizado!</h1>
            <p className="text-body-md text-on-surface-variant">
              {examen?.nombre ?? 'Tu examen'} · quedó guardado y no se puede modificar.
            </p>
          </div>
        </div>

        <div className="grid lg:grid-cols-3 gap-lg items-start">
          {/* Izquierda: ficha de resultados + estado de supervisión */}
          <main className="lg:col-span-2 space-y-lg min-w-0">
            <div className="rounded-2xl border border-outline-variant/50 bg-surface-container-lowest overflow-hidden divide-y divide-outline-variant/30">
              {notaPendiente ? (
                <div className="px-lg py-8 text-center text-on-surface-variant space-y-base">
                  <Icon name="lock_clock" className="text-[28px] text-warning" fill />
                  <p className="text-body-md text-on-surface">Tus resultados aún no están disponibles.</p>
                  <p className="text-label-md">
                    La nota{nota?.revision_disponible ? ' y la revisión' : ''} se publican cuando cierra el examen
                    {nota?.cierre ? <> (<strong>{fmtFecha(nota.cierre)}</strong>)</> : ''}.
                  </p>
                </div>
              ) : ficha.length > 0 ? (
                ficha.map((f) => (
                  <div key={f.label} className="flex items-center gap-md px-lg py-4">
                    <Icon name={f.icono} className={`text-[22px] ${f.color}`} fill />
                    <span className="flex-1 text-label-md text-on-surface-variant">{f.label}</span>
                    <span className="text-body-lg font-bold text-on-surface tabular-nums">{f.valor}</span>
                  </div>
                ))
              ) : (
                <div className="px-lg py-8 text-center text-on-surface-variant">
                  <Icon name="progress_activity" className="text-[24px] ae-spin" />
                  <p className="mt-base text-label-md">Corrigiendo tu examen…</p>
                </div>
              )}
              {pct != null && (
                <div className="flex items-center gap-md px-lg py-4 bg-surface-container-low/50">
                  <Icon name="percent" className="text-[22px] text-primary" fill />
                  <span className="flex-1 text-label-md text-on-surface-variant">Porcentaje de acierto</span>
                  <span className="text-body-lg font-bold text-on-surface tabular-nums">{pct}%</span>
                </div>
              )}
            </div>

            {/* Estado de supervisión (L2.5) */}
            <div className={`rounded-2xl border p-lg ${irARevision ? 'border-warning/30 bg-warning-container/25' : 'border-success/30 bg-success-container/25'}`}>
              <div className="flex items-start gap-md">
                <Icon name={irARevision ? 'gavel' : 'verified_user'} className={`text-[24px] shrink-0 ${irARevision ? 'text-warning' : 'text-success'}`} fill />
                <div>
                  <p className="text-label-lg font-semibold text-on-surface">
                    {irARevision ? 'Entra a revisión académica' : 'Sin incidencias relevantes'}
                  </p>
                  <p className="text-label-md text-on-surface-variant mt-0.5">
                    {irARevision
                      ? <>Tu sesión alcanzó o superó el umbral establecido ({umbralEfectivo} puntos). Un tutor la revisará y confirmará tu nota.</>
                      : 'Tu sesión no presenta incidencias que requieran revisión adicional.'}
                  </p>
                </div>
              </div>
            </div>
          </main>

          {/* Derecha: nota (nota + estado JUNTOS, sin estrella) + acciones */}
          <aside className="lg:sticky lg:top-6 space-y-md">
            <Card className="space-y-md text-center">
              {notaPendiente ? (
                <div className="py-base space-y-base">
                  <Icon name="lock_clock" className="text-[28px] text-warning" fill />
                  <p className="text-label-md font-semibold text-on-surface">Nota no disponible todavía</p>
                  <p className="text-label-sm text-on-surface-variant">
                    Se publica al cerrar el examen{nota?.cierre ? <><br /><strong>{fmtFecha(nota.cierre)}</strong></> : ''}.
                  </p>
                </div>
              ) : tieneNota ? (
                <>
                  <p className="text-label-sm font-semibold text-on-surface-variant uppercase tracking-wide">
                    {irARevision ? 'Nota preliminar' : 'Tu nota'}
                  </p>
                  {/* Un solo chip: estado primero, luego la nota. */}
                  <span
                    className={`inline-flex items-center gap-sm rounded-2xl px-md py-base font-bold ${
                      nota!.aprobado
                        ? 'bg-success-container text-success'
                        : 'bg-error-container text-on-error-container'
                    }`}
                  >
                    {nota!.aprobado != null && (
                      <span className="text-headline-sm leading-none">{nota!.aprobado ? 'Aprobado' : 'Desaprobado'}</span>
                    )}
                    <span className="text-headline-sm opacity-50">·</span>
                    <span className="text-headline-sm leading-none">{nota!.nota} / {notaMax}</span>
                  </span>
                  {puedeRevisar && (
                    <Button variant="secondary" icon="fact_check" onClick={revisar} className="w-full">
                      Revisar mis respuestas
                    </Button>
                  )}
                </>
              ) : (
                <div className="py-base text-on-surface-variant">
                  <Icon name="progress_activity" className="text-[24px] ae-spin" />
                  <p className="mt-base text-label-md">Calculando tu nota…</p>
                </div>
              )}
            </Card>

            <Button variant="outline" icon="home" onClick={volver} className="w-full">
              Volver al inicio
            </Button>
          </aside>
        </div>
      </div>
    </StudentShell>
  );
}
