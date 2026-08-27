/**
 * PreviewPreguntaModal — ver una pregunta del banco como la ve el alumno (c-78 E-08).
 *
 * Sin esto, la única forma de saber si una pregunta quedó bien importada era tomar
 * el examen. Muestra el enunciado, las opciones y, en las cloze, los huecos con sus
 * alternativas.
 *
 * Marca cuál es la correcta a propósito: el destinatario es el docente revisando SU
 * banco, y el sentido de la vista previa es chequear que esté bien marcada. Al
 * alumno esa información no le llega nunca (D3, se filtra server-side).
 */
import { useEffect, useState } from 'react';
import { Button, Icon, LoadingSpinner } from '../../ui/components';
import {
  previewPreguntaBanco,
  type PreguntaPreview,
} from '../../lib/apiAdmin/bancoPreguntasApi';
import { limpiarEnunciadoCloze } from '../../lib/cloze';

const TIPO_LABEL: Record<string, string> = {
  multichoice: 'Opción múltiple',
  truefalse: 'Verdadero / Falso',
  cloze: 'Cloze (completar)',
  shortanswer: 'Respuesta corta',
  matching: 'Relacionar',
};

interface Props {
  preguntaId: string | null;
  onCerrar: () => void;
}

export function PreviewPreguntaModal({ preguntaId, onCerrar }: Props) {
  const [pregunta, setPregunta] = useState<PreguntaPreview | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!preguntaId) {
      setPregunta(null);
      setError(null);
      return;
    }
    let cancelado = false;
    setCargando(true);
    setError(null);
    previewPreguntaBanco(preguntaId)
      .then((p) => {
        if (!cancelado) setPregunta(p);
      })
      .catch((err: unknown) => {
        // D16: un fallo de carga NO se renderiza como "la pregunta está vacía".
        if (!cancelado) {
          setError(
            err instanceof Error ? err.message : 'No se pudo cargar la pregunta.',
          );
        }
      })
      .finally(() => {
        if (!cancelado) setCargando(false);
      });
    return () => {
      cancelado = true;
    };
  }, [preguntaId]);

  if (!preguntaId) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onCerrar} />
      <div className="relative z-10 w-full max-w-2xl bg-white rounded-2xl shadow-xl flex flex-col max-h-[90vh]">
        <div className="flex items-center gap-3 px-6 pt-6 pb-4 border-b border-outline-variant/30">
          <div className="flex-1 min-w-0">
            <h2 className="text-title-md font-semibold text-on-surface">
              Vista previa
            </h2>
            <p className="text-label-md text-on-surface-variant">
              Así se ve la pregunta cuando la rinde un alumno
            </p>
          </div>
          <button
            onClick={onCerrar}
            aria-label="Cerrar vista previa"
            className="p-1.5 rounded-lg hover:bg-surface-100 text-on-surface-variant"
          >
            <Icon name="close" className="text-[20px]" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {cargando && <LoadingSpinner size="sm" label="Cargando pregunta…" />}

          {error && (
            <div
              role="alert"
              className="flex items-center gap-sm text-error bg-error-container/40 rounded-md px-3 py-2.5 text-label-sm"
            >
              <Icon name="error" className="text-[18px] shrink-0" fill />
              {error}
            </div>
          )}

          {pregunta && !cargando && !error && (
            <>
              <span className="inline-block rounded-full bg-surface-200 px-2.5 py-0.5 text-label-sm text-on-surface-variant">
                {TIPO_LABEL[pregunta.tipo] ?? pregunta.tipo}
              </span>

              <div
                className="text-body-md text-on-surface [&_img]:max-w-full [&_img]:h-auto"
                // El enunciado viene de Moodle en HTML (negritas, listas, código,
                // imágenes embebidas). Renderizarlo como texto plano mostraría las
                // etiquetas crudas y la vista previa no serviría para lo que es.
                //
                // En las CLOZE el enunciado trae además la sintaxis de los huecos
                // ({1:MULTICHOICE_S:=correcta#feedback~otra#feedback}), que embebe la
                // respuesta correcta Y el feedback de cada opción. Volcarla tal cual
                // hacía que la pantalla que promete "así se ve cuando la rinde un
                // alumno" mostrara justo lo contrario: un bloque ilegible con las
                // soluciones a la vista. Los huecos ya se listan abajo, uno por uno.
                dangerouslySetInnerHTML={{
                  __html:
                    pregunta.tipo === 'cloze'
                      ? limpiarEnunciadoCloze(pregunta.enunciado)
                      : pregunta.enunciado,
                }}
              />

              {pregunta.opciones.length > 0 && (
                <ul className="space-y-2">
                  {pregunta.opciones.map((o) => (
                    <li
                      key={`${o.orden}-${o.texto}`}
                      className={`flex items-start gap-2.5 rounded-lg border px-3 py-2 ${
                        o.es_correcta
                          ? 'border-success/40 bg-success-container/30'
                          : 'border-outline-variant/40'
                      }`}
                    >
                      <Icon
                        name={o.es_correcta ? 'check_circle' : 'radio_button_unchecked'}
                        className={`text-[18px] shrink-0 mt-0.5 ${
                          o.es_correcta ? 'text-success' : 'text-on-surface-variant'
                        }`}
                      />
                      <span
                        className="text-body-md text-on-surface [&_img]:max-w-full"
                        dangerouslySetInnerHTML={{ __html: o.texto }}
                      />
                    </li>
                  ))}
                </ul>
              )}

              {pregunta.blanks.length > 0 && (
                <div className="space-y-3">
                  <p className="text-label-sm font-medium text-on-surface-variant">
                    Huecos a completar
                  </p>
                  {pregunta.blanks.map((b) => (
                    <div
                      key={b.orden}
                      className="rounded-xl border border-outline-variant/40 px-3 py-2.5"
                    >
                      <p className="text-label-sm text-on-surface-variant">
                        Hueco {b.orden + 1} ·{' '}
                        {b.tipo === 'shortanswer' ? 'escribe la respuesta' : 'elige una'}
                      </p>
                      {b.opciones.length > 0 ? (
                        <ul className="mt-1.5 space-y-1">
                          {b.opciones.map((o) => (
                            <li
                              key={`${b.orden}-${o.orden}`}
                              className={`flex items-center gap-2 text-body-md ${
                                o.es_correcta
                                  ? 'text-success font-medium'
                                  : 'text-on-surface'
                              }`}
                            >
                              <Icon
                                name={
                                  o.es_correcta
                                    ? 'check_circle'
                                    : 'radio_button_unchecked'
                                }
                                className="text-[16px] shrink-0"
                              />
                              {o.texto}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="mt-1 text-label-sm text-on-surface-variant italic">
                          Sin alternativas cargadas.
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {pregunta.opciones.length === 0 && pregunta.blanks.length === 0 && (
                <p className="rounded-lg bg-error-container/30 px-3 py-2.5 text-label-md text-error">
                  Esta pregunta no tiene ninguna opción cargada. Al alumno le va a
                  llegar sin nada que responder y no se va a poder calificar.
                </p>
              )}
            </>
          )}
        </div>

        <div className="flex items-center justify-between gap-2 px-6 py-4 border-t border-outline-variant/30">
          <p className="text-label-sm text-on-surface-variant">
            El alumno no ve cuál es la correcta.
          </p>
          <Button variant="ghost" onClick={onCerrar}>
            Cerrar
          </Button>
        </div>
      </div>
    </div>
  );
}
