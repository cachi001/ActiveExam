/**
 * Par de botones «Exportar Excel» / «Exportar PDF».
 *
 * ## Por qué existe
 *
 * El mismo markup estaba copiado en `Auditoria` y `EstadisticasInstitucionales`
 * (verde con `grid_on`, rojo con `picture_as_pdf`, spinner mientras exporta), y
 * en `AlumnosComisionPanel` había derivado a otra cosa: dos botones `outline` sin
 * color y con el ícono `table_view`. Nadie los reconocía como los mismos botones.
 *
 * Es el resultado previsible de copiar y pegar: la tercera copia se escribió a
 * ojo. Un solo componente hace que no vuelva a pasar.
 *
 * ## El color no es decoración
 *
 * Verde para la planilla y rojo para el PDF es la convención que la gente ya trae
 * de Excel y de Acrobat: se distinguen sin leer. Por eso el color va acá adentro y
 * no se puede pasar por props.
 */

import { Icon } from './components';

export type FormatoExport = 'excel' | 'pdf';

interface Props {
  /** Formato que se está exportando ahora mismo, o `null` si ninguno. */
  exportando: FormatoExport | null;
  /** Deshabilita ambos (por ejemplo, mientras carga la tabla o si está vacía). */
  disabled?: boolean;
  /**
   * Etiquetas cortas («Excel» / «PDF»). Para barras densas —una fila de acordeón,
   * al lado de otras acciones— donde «Exportar Excel» desbalancea la fila. El
   * ícono y el color, que son lo que identifica al botón, no cambian.
   */
  compacto?: boolean;
  onExportar: (formato: FormatoExport) => void;
}

const BASE =
  'inline-flex items-center gap-1.5 rounded-md px-4 py-2 text-[13px] font-semibold text-white disabled:opacity-60';

export function ExportButtons({ exportando, disabled = false, compacto = false, onExportar }: Props) {
  const inerte = disabled || exportando !== null;
  return (
    <>
      <button
        type="button"
        onClick={() => onExportar('excel')}
        disabled={inerte}
        className={`${BASE} bg-success-600 hover:bg-success-700`}
      >
        <Icon
          name={exportando === 'excel' ? 'progress_activity' : 'grid_on'}
          className={`text-[16px] ${exportando === 'excel' ? 'ae-spin' : ''}`}
          fill
        />
        {exportando === 'excel' ? 'Exportando…' : compacto ? 'Excel' : 'Exportar Excel'}
      </button>
      <button
        type="button"
        onClick={() => onExportar('pdf')}
        disabled={inerte}
        className={`${BASE} bg-error-600 hover:bg-error-700`}
      >
        <Icon
          name={exportando === 'pdf' ? 'progress_activity' : 'picture_as_pdf'}
          className={`text-[16px] ${exportando === 'pdf' ? 'ae-spin' : ''}`}
          fill
        />
        {exportando === 'pdf' ? 'Exportando…' : compacto ? 'PDF' : 'Exportar PDF'}
      </button>
    </>
  );
}
