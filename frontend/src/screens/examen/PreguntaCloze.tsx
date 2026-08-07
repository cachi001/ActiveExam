/**
 * PreguntaCloze — renderiza una pregunta de tipo "cloze" (completar texto).
 *
 * Cada hueco (blank) puede ser:
 *  - MULTICHOICE / multichoice_nocase → <select> con las opciones disponibles
 *  - SHORTANSWER / shortanswer        → <input type="text"> libre
 *
 * El texto se arma concatenando texto_antes + control + texto_despues de cada blank
 * en orden, produciendo un flujo inline con los controles embebidos.
 */

import type { BlankRendicion } from '../../lib/examTakingApi';

interface Props {
  blanks: BlankRendicion[];
  /** blankId → valor seleccionado (opcionId para MULTICHOICE, texto libre para SHORTANSWER) */
  respuestas: Record<string, string>;
  onRespuesta: (blankId: string, valor: string) => void;
}

export function PreguntaCloze({ blanks, respuestas, onRespuesta }: Props) {
  const ordenados = [...blanks].sort((a, b) => a.orden - b.orden);

  return (
    <div className="text-body-md text-on-surface leading-loose">
      {ordenados.map((blank, idx) => {
        const tipoNorm = blank.tipo.toLowerCase();
        const valor = respuestas[blank.id] ?? '';
        const esMultichoice = tipoNorm === 'multichoice' || tipoNorm === 'multichoice_nocase';
        const seleccionado = valor !== '';
        const esUltimo = idx === ordenados.length - 1;

        return (
          <span key={blank.id}>
            {blank.texto_antes && <span>{blank.texto_antes}</span>}

            {esMultichoice ? (
              <select
                value={valor}
                onChange={(e) => onRespuesta(blank.id, e.target.value)}
                className={`mx-1 px-2 py-0.5 rounded-lg border text-body-md focus:outline-none focus:ring-2 focus:ring-primary transition-colors ${
                  seleccionado
                    ? 'border-primary bg-primary-fixed/30 text-on-surface'
                    : 'border-outline-variant bg-surface text-on-surface'
                }`}
              >
                <option value="">— elegir —</option>
                {blank.opciones.map((op) => (
                  <option key={op.id} value={op.id}>
                    {op.texto}
                  </option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                value={valor}
                onChange={(e) => onRespuesta(blank.id, e.target.value)}
                placeholder="Respuesta"
                className={`mx-1 px-2 py-0.5 rounded-lg border text-body-md focus:outline-none focus:ring-2 focus:ring-primary transition-colors w-32 ${
                  seleccionado
                    ? 'border-primary bg-primary-fixed/30 text-on-surface'
                    : 'border-outline-variant bg-surface text-on-surface'
                }`}
              />
            )}

            {esUltimo && blank.texto_despues && <span>{blank.texto_despues}</span>}
          </span>
        );
      })}
    </div>
  );
}
