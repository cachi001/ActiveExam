import { useEffect, useState } from 'react';
import { StudentShell } from '../ui/shells';
import { Icon, Button, Card } from '../ui/components';
import { ResultadoNotaChip } from '../ui/ResultadoNotaChip';
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
  const volver = () => { resetSesion(); navigate('/login'); };
  const revisar = () => { if (examenId) navigate(`/alumno/revision/${examenId}`); };

  // Filas de la ficha de resultados (con MI información del intento).
  return (
    // `ocultarNavegacion`: el cierre es el final del flujo de rendición, no una
    // pantalla de navegación. Con la sidebar, el alumno terminaba el examen y la
    // pantalla parecía otra sección más. Queda el «Volver al inicio» como salida.
    <StudentShell ocultarNavegacion>
      <div className="max-w-xl mx-auto space-y-lg text-center animate-in fade-in duration-300">
        <div className="w-20 h-20 rounded-full bg-success-container text-success flex items-center justify-center mx-auto">
          <Icon name="check_circle" className="text-[40px]" fill />
        </div>

        <div className="space-y-base">
          <h1 className="font-headline text-headline-lg text-on-surface">¡Examen finalizado!</h1>
          <p className="text-body-md text-on-surface-variant">
            {examen?.nombre ?? 'Tu examen'} quedó guardado y no se puede modificar.
          </p>
        </div>

        {/* Estado de supervisión (L2.5). Es lo ÚNICO que el alumno necesita saber
            además de que terminó: si su sesión entra a revisión humana. */}
        <div
          className={`rounded-2xl border p-lg text-left ${
            irARevision
              ? 'border-warning/30 bg-warning-container/25'
              : 'border-success/30 bg-success-container/25'
          }`}
        >
          <div className="flex items-start gap-md">
            <Icon
              name={irARevision ? 'gavel' : 'verified_user'}
              className={`text-[24px] shrink-0 ${irARevision ? 'text-warning' : 'text-success'}`}
              fill
            />
            <div>
              <p className="text-label-lg font-semibold text-on-surface">
                {irARevision ? 'Entra a revisión académica' : 'Sin incidencias relevantes'}
              </p>
              <p className="text-label-md text-on-surface-variant mt-0.5">
                {irARevision ? (
                  <>
                    Tu sesión alcanzó o superó el umbral establecido ({umbralEfectivo} puntos).
                    Un tutor la revisará y confirmará tu nota.
                  </>
                ) : (
                  'Tu sesión no presenta incidencias que requieran revisión adicional.'
                )}
              </p>
            </div>
          </div>
        </div>

        {/* La nota SOLO cuando ya se puede ver. Antes, con la nota pendiente, se
            mostraban dos carteles ("tus resultados aún no están disponibles" y
            "nota no disponible todavía") que decían lo mismo y no aportaban nada:
            si no la va a ver, no hace falta anunciárselo dos veces. */}
        {tieneNota && !notaPendiente && (
          <Card className="space-y-md text-center">
            <p className="text-label-sm font-semibold text-on-surface-variant uppercase tracking-wide">
              {irARevision ? 'Nota preliminar' : 'Tu nota'}
            </p>
            <span
              className={`inline-flex items-center gap-sm rounded-2xl px-md py-base font-bold ${
                nota!.aprobado
                  ? 'bg-success-container text-success'
                  : 'bg-error-container text-on-error-container'
              }`}
            >
              {/* El resultado lo define el BACKEND: escrito a mano acá, esta
                  pantalla decía "Aprobado" sobre una nota que la del docente ya
                  mostraba como "En revisión" o "Anulada". */}
              <ResultadoNotaChip resultado={nota!.resultado} />
              <span className="text-headline-sm opacity-50">·</span>
              <span className="text-headline-sm leading-none">
                {nota!.nota} / {notaMax}
              </span>
            </span>
            {puedeRevisar && (
              <Button variant="secondary" icon="fact_check" onClick={revisar} className="w-full">
                Revisar mis respuestas
              </Button>
            )}
          </Card>
        )}

        <Button icon="home" onClick={volver} className="mx-auto">
          Volver al inicio
        </Button>
      </div>
    </StudentShell>
  );
}
