/**
 * QuestionNavigator — navegador de preguntas estilo Moodle para el examen.
 *
 * Muestra una grilla de botones numerados (1..N) con tres estados visuales:
 *  - actual    → bg-primary text-on-primary   (azul institucional)
 *  - respondida → bg-success text-on-primary   (verde)
 *  - sin resp. → bg-surface-container-low text-on-surface-variant (neutro)
 *
 * Cada botón tiene aria-label accesible e invoca onIr con el índice 0-based.
 * Diseño responsivo: flex-wrap, mínimo táctil w-10 h-10 (40×40 px).
 */

interface QuestionNavigatorProps {
  /** Cantidad total de preguntas del examen. */
  total: number;
  /** Índice 0-based de la pregunta que se está mostrando ahora. */
  indiceActual: number;
  /** Conjunto de índices 0-based de preguntas que ya tienen una respuesta. */
  respondidas: Set<number>;
  /** Callback invocado con el índice 0-based al presionar un botón. */
  onIr: (indice: number) => void;
}

export function QuestionNavigator({
  total,
  indiceActual,
  respondidas,
  onIr,
}: QuestionNavigatorProps) {
  return (
    <div className="flex flex-wrap gap-base py-sm">
      {Array.from({ length: total }, (_, i) => {
        const numero = i + 1;
        const esActual = i === indiceActual;
        const esRespondida = respondidas.has(i);

        // Tres estados visuales con tokens del design system (tailwind.config.js)
        let clases: string;
        if (esActual) {
          clases =
            'w-10 h-10 flex items-center justify-center rounded-lg text-label-sm font-semibold transition-colors bg-primary text-on-primary';
        } else if (esRespondida) {
          clases =
            'w-10 h-10 flex items-center justify-center rounded-lg text-label-sm font-semibold transition-colors bg-success text-on-primary';
        } else {
          clases =
            'w-10 h-10 flex items-center justify-center rounded-lg text-label-sm font-semibold transition-colors bg-surface-container-low text-on-surface-variant hover:bg-surface-container';
        }

        const ariaLabel = esRespondida
          ? `Pregunta ${numero}, respondida`
          : `Pregunta ${numero}, sin responder`;

        return (
          <button
            key={i}
            onClick={() => onIr(i)}
            aria-label={ariaLabel}
            aria-current={esActual ? 'true' : undefined}
            className={clases}
          >
            {numero}
          </button>
        );
      })}
    </div>
  );
}
