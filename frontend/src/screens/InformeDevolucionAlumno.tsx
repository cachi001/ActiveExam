/**
 * InformeDevolucionAlumno — Informe de devolución del alumno (C-71 slice 2, D12).
 *
 * Ruta: /alumno/informe/:sessionId. Alcanzable desde MiNota SOLO cuando el
 * veredicto es `anulado_por_fraude` (transparencia acotada / debido proceso).
 *
 * Consume GET /exam-content/mis-notas/{sessionId}/informe (scoped al titular). Si
 * la nota no fue anulada por fraude, el backend responde 404 → mostramos "no
 * disponible" (minimización, Ley 25.326). Muestra: la decisión y el motivo, el
 * análisis por señal (re-inferido server-side) y las capturas con URL firmada
 * (expira 15 min). El acceso queda auditado server-side como derecho de acceso.
 */
import { useEffect, useState } from 'react';
import { StudentShell } from '../ui/shells';
import { Card, Icon, LoadingSpinner, BackButton, SectionTitle, Badge } from '../ui/components';
import { api } from '../lib/api';
import { useRouteParam, useNavigate } from '../lib/router';
import {
  SEVERIDAD_TONE,
  severidadLabel,
  tipoEventoLabel,
  veredictoReinferenciaLabel,
} from '../lib/apiLabels';
import type { InformeDevolucion, Severidad } from '../lib/types';

export default function InformeDevolucionAlumno() {
  const sessionId = useRouteParam('sessionId');
  const navigate = useNavigate();
  const [cargando, setCargando] = useState(true);
  const [informe, setInforme] = useState<InformeDevolucion | null>(null);

  useEffect(() => {
    if (!sessionId) {
      setCargando(false);
      return;
    }
    setCargando(true);
    (async () => {
      const data = await api.informeDevolucion(sessionId);
      setInforme(data);
      setCargando(false);
    })();
  }, [sessionId]);

  return (
    <StudentShell backTo="/alumno/mis-examenes">
      <div className="max-w-3xl mx-auto space-y-lg animate-in fade-in duration-500">
        <BackButton onClick={() => navigate('/alumno/mis-examenes')} label="Volver a mis exámenes" />
        <h1 className="font-headline text-headline-md text-on-surface">Informe de devolución</h1>

        {cargando && (
          <Card className="text-center py-xl text-on-surface-variant space-y-base">
            <LoadingSpinner size="md" label="Cargando informe…" />
          </Card>
        )}

        {!cargando && !informe && (
          <Card className="text-center py-xl space-y-base">
            <Icon name="visibility_off" className="text-on-surface-variant text-[40px]" />
            <h3 className="font-headline text-title-lg text-on-surface">Informe no disponible</h3>
            <p className="text-label-md text-on-surface-variant">
              Este informe de devolución solo está disponible cuando una nota fue anulada por
              fraude. Si creés que esto es un error, comunicate con tu institución.
            </p>
          </Card>
        )}

        {!cargando && informe && (
          <>
            <Card className="space-y-md">
              <div className="flex items-center justify-between gap-md flex-wrap">
                <SectionTitle sub="Resultado de la revisión de tu sesión.">
                  Decisión
                </SectionTitle>
                <Badge tone="error" dot>
                  Nota anulada por fraude
                </Badge>
              </div>
              <div className="rounded-xl bg-error-container/40 border border-error/30 p-md space-y-base">
                <p className="text-label-sm uppercase tracking-wide text-on-surface-variant">
                  Motivo
                </p>
                <p className="text-body-md text-on-surface">
                  {informe.motivo?.trim() || 'Sin motivo registrado.'}
                </p>
              </div>
              <p className="text-label-sm text-on-surface-variant">
                La decisión es siempre humana; el sistema nunca sanciona automáticamente. Podés
                iniciar una apelación ante tu institución.
              </p>
            </Card>

            <Card className="space-y-md">
              <SectionTitle sub="Qué indicó cada detector durante tu sesión (verificado por el servidor).">
                Análisis por señal
              </SectionTitle>
              {informe.senales.length === 0 ? (
                <p className="text-label-md text-on-surface-variant">Sin señales registradas.</p>
              ) : (
                <div className="space-y-sm">
                  {informe.senales.map((s, i) => (
                    <div
                      key={`${s.tipo}-${i}`}
                      className="flex items-center justify-between gap-md rounded-xl border
                        border-outline-variant/60 bg-white p-sm flex-wrap"
                    >
                      <div className="min-w-0">
                        {/* Nombre legible, NUNCA el código interno: esta es la
                            pantalla con la que el alumno entiende (y puede
                            discutir) lo que se registró en su examen. */}
                        <p className="text-label-md font-semibold text-on-surface">
                          {tipoEventoLabel(s.tipo)}
                        </p>
                        <p className="text-label-sm text-on-surface-variant">
                          {s.ocurrencias} {s.ocurrencias === 1 ? 'ocurrencia' : 'ocurrencias'}
                          {' · '}
                          {veredictoReinferenciaLabel(s.veredicto_reinferencia)}
                          {s.face_count_servidor != null
                            ? ` · rostros detectados por el servidor: ${s.face_count_servidor}`
                            : ''}
                        </p>
                      </div>
                      {/* El color acompaña a la palabra: "Alta" en rojo y "Baja"
                          en verde se distinguen sin leer. Antes todo lo que no
                          fuera alta/critico salía gris e indistinguible. */}
                      <Badge tone={SEVERIDAD_TONE[s.severidad as Severidad] ?? 'neutral'} dot>
                        {severidadLabel(s.severidad)}
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            <Card className="space-y-md">
              {/* El texto anterior era "Enlaces temporales (expiran a los 15
                  minutos)" y se leía como que LA PRUEBA se borra en 15 minutos.
                  Lo que caduca es el enlace de acceso, por seguridad; la
                  evidencia queda guardada. Decirlo mal, en la pantalla donde el
                  alumno se defiende, es hacerle creer que tiene que apurarse. */}
              <SectionTitle sub="Las imágenes quedan guardadas. Por seguridad, el enlace de acceso caduca a los 15 minutos: si vence, volvé a abrir esta página y se genera uno nuevo.">
                Capturas de evidencia
              </SectionTitle>
              {informe.capturas.length === 0 ? (
                <p className="text-label-md text-on-surface-variant">Sin capturas asociadas.</p>
              ) : (
                <ul className="space-y-sm">
                  {informe.capturas.map((c, i) => (
                    <li
                      key={`${c.object_key}-${i}`}
                      className="flex items-center justify-between gap-md rounded-xl border
                        border-outline-variant/60 bg-white p-sm flex-wrap"
                    >
                      <div className="min-w-0">
                        {/* Cada captura dice DE QUÉ señal salió y CUÁNDO. Antes
                            eran "Ver captura 1, 2, 3": imposible relacionarlas
                            con lo que se le imputa al alumno. */}
                        <p className="text-label-md font-semibold text-on-surface">
                          {c.tipo_evento ? tipoEventoLabel(c.tipo_evento) : `Captura ${i + 1}`}
                        </p>
                        {c.ocurrio_en && (
                          <p className="text-label-sm text-on-surface-variant">
                            {new Date(c.ocurrio_en).toLocaleString('es-AR', {
                              day: '2-digit', month: '2-digit', year: 'numeric',
                              hour: '2-digit', minute: '2-digit',
                            })}
                          </p>
                        )}
                      </div>
                      <div className="flex items-center gap-sm shrink-0">
                        {c.severidad && (
                          <Badge tone={SEVERIDAD_TONE[c.severidad as Severidad] ?? 'neutral'} dot>
                            {severidadLabel(c.severidad)}
                          </Badge>
                        )}
                        <a
                          href={c.url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-base text-label-md font-semibold text-primary
                            hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 rounded"
                        >
                          <Icon name="image" className="text-[18px]" />
                          Ver imagen
                        </a>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </>
        )}
      </div>
    </StudentShell>
  );
}
