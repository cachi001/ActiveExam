/**
 * ChipMultiSelect — patrón genérico de selección múltiple con chips.
 *
 * Por qué existe: ComisionMultiSelect, AsignarDocenteDialog y
 * AsignarResponsableDialog resolvían "elegir varios de una lista" con tres
 * variantes del mismo patrón visual (select + lista aparte con botón Quitar,
 * cada uno con su propio marcado). El sistema de referencia del dueño usa un
 * único patrón para esto: los elegidos se muestran como chips con el mismo
 * peso visual (no hay "principal" ni orden), con una X para sacarlos, y el
 * desplegable ofrece solo lo que falta. Este componente es la versión
 * agnóstica de dominio de ese patrón — no sabe qué es una comisión o un
 * tutor, ni llama a ningún endpoint: cada pantalla le pasa sus propias
 * opciones y decide qué hacer al agregar o quitar (la llamada de red sigue
 * siendo de a uno, igual que antes; este componente no la reemplaza).
 */
import { Icon } from './components';

export interface ChipMultiSelectOption {
  id: string;
  /** Texto del <option> en el desplegable. Puede llevar info extra (ej. "Nombre · legajo"). */
  textoOpcion: string;
  /** Texto del chip y del aria-label "Quitar {texto}". Por defecto, igual a textoOpcion. */
  textoChip?: string;
}

export interface ChipMultiSelectProps {
  /** Opciones ya elegidas, mostradas como chips. */
  seleccionados: ChipMultiSelectOption[];
  /** Opciones que todavía se pueden elegir (quien llama ya sacó las elegidas). */
  disponibles: ChipMultiSelectOption[];
  onAgregar: (id: string) => void;
  onQuitar: (id: string) => void;
  /**
   * Texto de la opción vacía (placeholder) del desplegable. Lo decide quien
   * llama porque el mensaje cambia según el estado (cargando, sin candidatos,
   * sin candidatos que falten) y esa lógica es de cada pantalla.
   */
  textoOpcionVacia: string;
  /** Deshabilita chips y desplegable (ej. mientras guarda, o sin opciones). */
  disabled?: boolean;
  id?: string;
  className?: string;
}

const DEFAULT_CLASS =
  'rounded-lg border border-surface-300 px-3 py-2 text-label-md text-on-surface focus:border-primary focus:outline-none disabled:bg-surface-100 disabled:text-on-surface-variant disabled:cursor-not-allowed';

export function ChipMultiSelect({
  seleccionados,
  disponibles,
  onAgregar,
  onQuitar,
  textoOpcionVacia,
  disabled = false,
  id,
  className = DEFAULT_CLASS,
}: ChipMultiSelectProps) {
  return (
    <div className="flex flex-col gap-2">
      {seleccionados.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {seleccionados.map((op) => {
            const texto = op.textoChip ?? op.textoOpcion;
            return (
              <span
                key={op.id}
                className="inline-flex items-center gap-1 rounded-full bg-primary/10 text-primary border border-primary/30 pl-2.5 pr-1 py-0.5 text-label-sm"
              >
                {texto}
                <button
                  type="button"
                  aria-label={`Quitar ${texto}`}
                  disabled={disabled}
                  onClick={() => onQuitar(op.id)}
                  className="rounded-full p-0.5 hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Icon name="close" className="text-[14px]" />
                </button>
              </span>
            );
          })}
        </div>
      )}

      <select
        id={id}
        value=""
        disabled={disabled}
        onChange={(e) => {
          // El select nunca "recuerda" un valor elegido (queda en ""): el elegido
          // pasa a ser un chip y desaparece de las opciones, así que no hay nada
          // que dejar seleccionado en el propio <select>.
          if (e.target.value) onAgregar(e.target.value);
        }}
        className={className}
      >
        <option value="">{textoOpcionVacia}</option>
        {disponibles.map((op) => (
          <option key={op.id} value={op.id}>
            {op.textoOpcion}
          </option>
        ))}
      </select>
    </div>
  );
}

export default ChipMultiSelect;
