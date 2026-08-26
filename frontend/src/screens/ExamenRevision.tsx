/**
 * ExamenRevision — revisión post-examen (read-only) del alumno (C-69).
 *
 * Desktop-first: ocupa todo el ancho. NO despliega todo en cascada — usa un
 * navegador de preguntas (números con color según resultado) + el detalle de la
 * pregunta seleccionada. Corrección: VERDE = correcta, ROJO = elegida-mal.
 *
 * Los datos (incl. es_correcta) vienen de GET /exam-content/{id}/revision, que solo
 * los expone al dueño y con el intento finalizado (excepción a D3, estilo Moodle).
 */
import { useEffect, useState } from 'react';
import { StudentShell } from '../ui/shells';
import { Icon, Button, Card } from '../ui/components';
import { useNavigate, useRouteParam } from '../lib/router';
import { useApp } from '../lib/store';
import { api } from '../lib/api';
import type { RevisionExamen, OpcionRevision, PreguntaRevision } from '../lib/types';
import { renderTextoConCodigo } from './examen/renderTextoConCodigo';
import { textoResultadoRevision } from './ExamenRevision.texto';

/** Estado de una pregunta para color del navegador. */
type EstadoPregunta = 'correcta' | 'incorrecta' | 'sin_responder';

function estadoPregunta(p: PreguntaRevision): EstadoPregunta {
  if (!p.respondida) return 'sin_responder';
  return p.acertada ? 'correcta' : 'incorrecta';
}

const NAV_COLORES: Record<EstadoPregunta, string> = {
  correcta: 'bg-success-container text-success border-success/50',
  incorrecta: 'bg-error-container text-on-error-container border-error/50',
  sin_responder: 'bg-warning-container text-warning border-warning/50',
};

/** Estilo/estado de cada opción en el detalle. */
function estiloOpcion(o: OpcionRevision): {
  clase: string;
  icono: string | null;
  etiqueta: string | null;
  color: string;
} {
  if (o.es_correcta) {
    return {
      clase: 'border-success/50 bg-success-container/40',
      icono: 'check_circle',
      etiqueta: o.elegida ? 'Tu respuesta · correcta' : 'Respuesta correcta',
      color: 'text-success',
    };
  }
  if (o.elegida) {
    return {
      clase: 'border-error/50 bg-error-container/40',
      icono: 'cancel',
      etiqueta: 'Tu respuesta',
      color: 'text-error',
    };
  }
  return {
    clase: 'border-outline-variant/50 bg-surface-container-lowest',
    icono: null,
    etiqueta: null,
    color: 'text-on-surface-variant',
  };
}

export default function ExamenRevision() {
  const navigate = useNavigate();
  const paramId = useRouteParam('examenId');
  const examen = useApp((s) => s.examenActivo);
  const examenId = paramId ?? examen?.examen_contenido_id ?? examen?.id ?? null;

  const [revision, setRevision] = useState<RevisionExamen | null>(null);
  const [cargando, setCargando] = useState(true);
  const [indice, setIndice] = useState(0);

  useEffect(() => {
    if (!examenId) {
      setCargando(false);
      return;
    }
    let cancelado = false;
    void api.revisionExamen(examenId).then((r) => {
      if (cancelado) return;
      setRevision(r);
      setCargando(false);
    });
    return () => {
      cancelado = true;
    };
  }, [examenId]);

  const preguntas = revision?.preguntas ?? [];
  const preguntaActual = preguntas[indice] ?? null;
  const fmtFecha = (iso?: string | null) =>
    iso ? new Date(iso).toLocaleString('es-AR', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';

  const volver = () => navigate('/alumno/mis-examenes');

  return (
    <StudentShell backTo="/alumno/mis-examenes">
      <div className="w-full space-y-lg animate-in fade-in duration-300">
        <div className="flex items-end justify-between gap-md flex-wrap">
          <div>
            <p className="text-label-sm font-semibold text-on-surface-variant uppercase tracking-wide">
              Revisión del examen
            </p>
            <h1 className="font-headline text-headline-md text-on-surface">
              {revision?.titulo ?? 'Examen'}
            </h1>
          </div>
          <Button variant="outline" size="sm" icon="arrow_back" onClick={volver}>
            Volver a Mis exámenes
          </Button>
        </div>

        {cargando ? (
          <Card className="text-center py-2xl text-on-surface-variant">
            <Icon name="progress_activity" className="text-[28px] ae-spin" />
            <p className="mt-base text-label-md">Cargando tu revisión…</p>
          </Card>
        ) : !revision ? (
          <Card className="text-center py-2xl space-y-base">
            <Icon name="info" className="text-[32px] text-on-surface-variant" />
            <p className="text-body-md text-on-surface">La revisión todavía no está disponible.</p>
            <p className="text-label-sm text-on-surface-variant">
              Se habilita cuando tu intento quedó finalizado y corregido.
            </p>
          </Card>
        ) : revision.disponible === false ? (
          <Card className="text-center py-2xl space-y-base">
            <Icon name="lock_clock" className="text-[36px] text-warning" fill />
            <p className="text-body-lg text-on-surface font-medium">Tus resultados aún no están disponibles</p>
            <p className="text-label-md text-on-surface-variant">
              La nota y la revisión se publican cuando cierra el examen
              {revision.cierre ? <> (<strong>{fmtFecha(revision.cierre)}</strong>)</> : ''}.
            </p>
          </Card>
        ) : (
          <>
            {/* Resumen: nota+estado JUNTOS a la izquierda + stats (full-width) */}
            <Card className="space-y-lg">
              <div className="flex items-center justify-between gap-lg flex-wrap">
                {/* Un solo chip: estado primero, luego la nota. */}
                {revision.nota != null ? (
                  <span
                    className={`inline-flex items-center gap-sm rounded-full px-md py-base font-bold ${
                      revision.aprobado
                        ? 'bg-success-container text-success'
                        : 'bg-error-container text-on-error-container'
                    }`}
                  >
                    <span className="text-headline-sm leading-none">{revision.aprobado ? 'Aprobado' : 'Desaprobado'}</span>
                    <span className="text-headline-sm opacity-50">·</span>
                    <span className="text-headline-sm leading-none">
                      {revision.nota}{revision.nota_maxima != null ? ` / ${revision.nota_maxima}` : ''}
                    </span>
                  </span>
                ) : (
                  <span className="inline-flex items-center text-headline-md font-bold text-on-surface-variant rounded-full bg-surface-container-high px-md py-base">—</span>
                )}
                {/* c-78: SIN la fórmula. Antes decía "la nota = correctas ÷ total
                    × 10", y el alumno no tiene por qué ver el mecanismo: invita a
                    discutir el redondeo en vez del contenido. Ve su resultado. */}
                <p className="text-label-md text-on-surface-variant max-w-md">
                  {textoResultadoRevision({
                    correctas: revision.correctas,
                    total: revision.total_preguntas,
                  })}
                </p>
              </div>

              <div className="grid grid-cols-3 gap-md">
                <div className="rounded-xl bg-success-container/50 py-md text-center">
                  <p className="text-headline-md font-bold text-success leading-none">{revision.correctas}</p>
                  <p className="text-label-sm text-on-surface-variant mt-base">Correctas</p>
                </div>
                <div className="rounded-xl bg-error-container/50 py-md text-center">
                  <p className="text-headline-md font-bold text-error leading-none">{revision.incorrectas}</p>
                  <p className="text-label-sm text-on-surface-variant mt-base">Incorrectas</p>
                </div>
                <div className="rounded-xl bg-warning-container/60 py-md text-center">
                  <p className="text-headline-md font-bold text-warning leading-none">{revision.sin_responder}</p>
                  <p className="text-label-sm text-on-surface-variant mt-base">Sin responder</p>
                </div>
              </div>
            </Card>

            {/* Si la corrección no está habilitada/disponible, mostramos solo el
                resumen (arriba) + este aviso — sin el detalle pregunta por pregunta. */}
            {revision.revision_disponible === false || preguntas.length === 0 ? (
              <Card className="text-center py-xl space-y-base">
                <Icon name="visibility_off" className="text-[28px] text-on-surface-variant" />
                <p className="text-body-md text-on-surface">La revisión detallada de respuestas no está habilitada para este examen.</p>
                <p className="text-label-sm text-on-surface-variant">
                  Ves tu nota y el resumen, pero el detalle de cada pregunta no está disponible.
                </p>
              </Card>
            ) : (
            /* Detalle (izq, ocupa el ancho) + navegador de preguntas (der) */
            <div className="grid lg:grid-cols-3 gap-lg items-start">
              <main className="lg:col-span-2 min-w-0">
                {preguntaActual && (
                  <Card className="space-y-lg">
                    <div className="flex items-start gap-md">
                      <span
                        className={`shrink-0 w-9 h-9 rounded-lg flex items-center justify-center text-label-md font-bold border ${
                          NAV_COLORES[estadoPregunta(preguntaActual)]
                        }`}
                      >
                        {indice + 1}
                      </span>
                      <div className="flex-1 min-w-0 space-y-base">
                        {preguntaActual.tipo !== 'cloze' && (
                          <p className="text-body-lg font-medium text-on-surface">
                            {renderTextoConCodigo(preguntaActual.enunciado, preguntaActual.id)}
                          </p>
                        )}
                        {!preguntaActual.respondida && (
                          <span className="inline-flex items-center gap-xs text-label-sm font-medium text-warning bg-warning-container/50 rounded-lg px-md py-base">
                            <Icon name="help" className="text-[16px]" fill />
                            No respondiste esta pregunta
                          </span>
                        )}
                      </div>
                    </div>

                    {preguntaActual.tipo === 'cloze' ? (
                      <div className="text-body-md text-on-surface leading-loose whitespace-pre-wrap rounded-xl border border-outline-variant/60 bg-surface-container-low p-md">
                        {(preguntaActual.blanks_revisados ?? []).map((b, idx, arr) => {
                          const esUltimo = idx === arr.length - 1;
                          return (
                            <span key={b.blank_id}>
                              {b.texto_antes && (
                                <span>{renderTextoConCodigo(b.texto_antes, `${b.blank_id}-antes`)}</span>
                              )}
                              <span
                                className={`inline-flex items-center gap-xs mx-1 rounded-lg border px-2 py-0.5 font-medium ${
                                  b.respuesta_alumno == null
                                    ? 'border-outline-variant/50 bg-surface-container text-on-surface-variant'
                                    : b.es_correcta
                                    ? 'border-success/50 bg-success-container/40 text-success'
                                    : 'border-error/50 bg-error-container/40 text-error'
                                }`}
                              >
                                {b.respuesta_alumno == null ? (
                                  <>
                                    <Icon name="help" className="text-[16px] shrink-0" />
                                    <span className="italic">No respondido</span>
                                  </>
                                ) : (
                                  <>
                                    <Icon
                                      name={b.es_correcta ? 'check_circle' : 'cancel'}
                                      className="text-[16px] shrink-0"
                                      fill
                                    />
                                    <span>{b.respuesta_alumno}</span>
                                  </>
                                )}
                              </span>
                              {esUltimo && b.texto_despues && (
                                <span>{renderTextoConCodigo(b.texto_despues, `${b.blank_id}-despues`)}</span>
                              )}
                            </span>
                          );
                        })}
                      </div>
                    ) : (
                    <div className="space-y-md">
                      {preguntaActual.opciones.map((o) => {
                        const s = estiloOpcion(o);
                        return (
                          <div
                            key={o.id}
                            className={`flex items-center gap-md rounded-lg border px-md py-md ${s.clase}`}
                          >
                            {s.icono ? (
                              <Icon name={s.icono} className={`text-[22px] shrink-0 ${s.color}`} fill />
                            ) : (
                              <span className="w-[22px] shrink-0" />
                            )}
                            <span className="text-body-md text-on-surface flex-1">{o.texto}</span>
                            {s.etiqueta && (
                              <span className={`text-label-sm font-semibold whitespace-nowrap ${s.color}`}>
                                {s.etiqueta}
                              </span>
                            )}
                          </div>
                        );
                      })}
                    </div>
                    )}

                    <div className="flex items-center justify-between pt-base border-t border-outline-variant/30">
                      <Button
                        variant="outline"
                        size="sm"
                        icon="arrow_back"
                        onClick={() => setIndice((i) => Math.max(0, i - 1))}
                        disabled={indice === 0}
                      >
                        Anterior
                      </Button>
                      <span className="text-label-sm text-on-surface-variant">
                        Pregunta {indice + 1} de {preguntas.length}
                      </span>
                      <Button
                        variant="outline"
                        size="sm"
                        iconRight="arrow_forward"
                        onClick={() => setIndice((i) => Math.min(preguntas.length - 1, i + 1))}
                        disabled={indice >= preguntas.length - 1}
                      >
                        Siguiente
                      </Button>
                    </div>
                  </Card>
                )}
              </main>

              <aside className="lg:sticky lg:top-6 space-y-md">
                <Card className="space-y-md">
                  <h3 className="text-label-sm font-semibold text-on-surface-variant uppercase tracking-wide">
                    Preguntas
                  </h3>
                  <div className="grid grid-cols-6 lg:grid-cols-5 gap-sm">
                    {preguntas.map((p, i) => {
                      const est = estadoPregunta(p);
                      const activa = i === indice;
                      return (
                        <button
                          key={p.id}
                          type="button"
                          onClick={() => setIndice(i)}
                          className={`aspect-square rounded-lg border text-label-md font-bold flex items-center justify-center transition ${
                            NAV_COLORES[est]
                          } ${activa ? 'ring-2 ring-primary ring-offset-1' : 'hover:brightness-95'}`}
                        >
                          {i + 1}
                        </button>
                      );
                    })}
                  </div>
                  <div className="space-y-base pt-base border-t border-outline-variant/30">
                    <div className="flex items-center gap-sm text-label-sm text-on-surface-variant">
                      <span className="w-3 h-3 rounded bg-success-container border border-success/50" /> Correcta
                    </div>
                    <div className="flex items-center gap-sm text-label-sm text-on-surface-variant">
                      <span className="w-3 h-3 rounded bg-error-container border border-error/50" /> Incorrecta
                    </div>
                    <div className="flex items-center gap-sm text-label-sm text-on-surface-variant">
                      <span className="w-3 h-3 rounded bg-warning-container border border-warning/50" /> Sin responder
                    </div>
                  </div>
                </Card>
              </aside>
            </div>
            )}
          </>
        )}
      </div>
    </StudentShell>
  );
}
