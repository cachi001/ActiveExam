import { useEffect, useState } from 'react';
import { StudentShell } from '../ui/shells';
import { Icon, Button, Card } from '../ui/components';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api } from '../lib/api';
import { loadEffectiveConfig, getEffectiveConfig, resetEffectiveConfigCache } from '../config/effectiveConfigCache';
import type { NotaExamen } from '../lib/types';

export default function Cierre() {
  const navigate = useNavigate();
  const score = useApp((s) => s.scorePropio);
  const examen = useApp((s) => s.examenActivo);
  const resetSesion = useApp((s) => s.resetSesion);
  const proctoringSessionId = useApp((s) => s.proctoringSessionId);

  // Umbral de revisión: SIEMPRE de la config efectiva del sistema (no un literal).
  // Así la pantalla de cierre es coherente con la Cola de revisión.
  const [umbralRevision, setUmbralRevision] = useState<number | null>(null);
  // C-69: nota académica del examen recién rendido (fuente de verdad = backend).
  const [nota, setNota] = useState<NotaExamen | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        resetEffectiveConfigCache();
        await loadEffectiveConfig();
        setUmbralRevision(getEffectiveConfig()?.umbral_cola_revision ?? null);
      } catch { /* sin red: cae al fallback del examen */ }
    })();
  }, []);

  // Solo finalizar la sesión (setea finalizada_en en el backend). El detalle
  // completo de la sesión (GET /proctoring/sessions/{id}) es vista del
  // PROCTOR (403 para el alumno, RBAC intencional) — el alumno no la consulta.
  useEffect(() => {
    if (!proctoringSessionId) return;
    void api.finalizarSesionProctoring(proctoringSessionId).catch(() => null);
  }, [proctoringSessionId]);

  // C-69: traer la nota del examen recién rendido. Se intenta varias veces porque la
  // corrección server-side (write-back de Moodle) puede tardar un instante tras finalizar.
  useEffect(() => {
    if (!examen) return;
    const objetivoId = examen.examen_contenido_id ?? examen.id;
    let cancelado = false;
    let intentos = 0;
    const buscar = async () => {
      const notas = await api.misNotas().catch(() => []);
      if (cancelado) return;
      const match = notas.find((n) => n.examen_id === objetivoId);
      if (match) { setNota(match); return; }
      // Reintentar mientras la nota aún no esté disponible (máx ~5 intentos).
      if (++intentos < 5) setTimeout(buscar, 1500);
    };
    void buscar();
    return () => { cancelado = true; };
  }, [examen]);

  const umbralEfectivo = nota?.umbral_revision ?? umbralRevision ?? examen?.umbral_score ?? 70;
  // Reconciliar el cálculo local con el backend: si tenemos la nota, su `en_cola_revision`
  // (decidido server-side) MANDA sobre el cálculo local de score>=umbral.
  const irARevision = nota ? nota.en_cola_revision : score >= umbralEfectivo;
  const tieneNota = nota != null && nota.nota !== null && nota.nota !== undefined;

  const volver = () => { resetSesion(); navigate('/login'); };

  return (
    <StudentShell>
      <div className="max-w-xl lg:max-w-2xl mx-auto space-y-lg text-center animate-in zoom-in duration-500">
        <div className="w-20 h-20 rounded-full bg-success-container text-success flex items-center justify-center mx-auto">
          <Icon name="check_circle" className="text-[40px]" fill />
        </div>
        <div className="space-y-base">
          <h2 className="font-headline text-headline-lg text-on-surface">¡Examen finalizado!</h2>
          <p className="text-body-md text-on-surface-variant">
            Tu examen quedó guardado de forma segura. Nadie puede modificarlo después de que lo entregaste.
          </p>
        </div>

        {/* C-69: NOTA académica del examen. Si quedó en cola de revisión, se muestra
            como PRELIMINAR con la explicación; si no, como nota final. */}
        {tieneNota && (
          <Card className={`text-left ${irARevision ? 'bg-warning-container/40 border-warning-200' : 'bg-success-container/40 border-success/30'}`}>
            <div className="flex items-start gap-sm">
              <Icon name={irARevision ? 'hourglass_top' : 'grade'} className={irARevision ? 'text-warning' : 'text-success'} fill />
              <div className="min-w-0">
                <div className="flex items-center gap-sm flex-wrap">
                  <p className="text-headline-sm font-semibold text-on-surface">
                    {irARevision ? 'Tu nota preliminar: ' : 'Tu nota: '}
                    {nota!.nota}
                    {nota!.nota_maxima != null ? ` / ${nota!.nota_maxima}` : ''}
                  </p>
                  {nota!.aprobado != null && (
                    <span
                      className={`inline-flex items-center gap-xs text-label-sm font-medium rounded-full px-sm py-0.5 ${
                        nota!.aprobado
                          ? 'bg-success-container text-success'
                          : 'bg-error-container text-on-error-container'
                      }`}
                    >
                      <Icon name={nota!.aprobado ? 'check_circle' : 'cancel'} className="text-[14px]" fill />
                      {nota!.aprobado ? 'Aprobado' : 'Desaprobado'}
                    </span>
                  )}
                </div>
                <p className="text-label-md text-on-surface mt-base">
                  {irARevision
                    ? <>Tu examen quedó <strong>en cola de revisión</strong> por los eventos registrados durante la supervisión. Un docente la revisará y confirmará tu nota.</>
                    : 'Esta es tu nota final del examen.'}
                </p>
              </div>
            </div>
          </Card>
        )}

        <Card className={`text-left ${irARevision ? 'bg-warning-container/40 border-warning-200' : 'bg-success-container/40 border-success/30'}`}>
          <div className="flex items-start gap-sm">
            <Icon name={irARevision ? 'gavel' : 'verified_user'} className={irARevision ? 'text-warning' : 'text-success'} fill />
            <p className="text-label-md text-on-surface">
              {irARevision
                ? <>Tu sesión alcanzó o superó el umbral establecido ({umbralEfectivo} puntos) y entra a la cola de revisión académica.</>
                : 'Tu sesión no presenta incidencias relevantes. No se requiere revisión adicional.'}
            </p>
          </div>
        </Card>

        <Button variant="outline" icon="home" onClick={volver} className="mx-auto">Volver al inicio</Button>
      </div>
    </StudentShell>
  );
}
