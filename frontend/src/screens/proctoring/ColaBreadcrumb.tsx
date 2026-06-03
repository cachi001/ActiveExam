/**
 * ColaBreadcrumb — Ruta de navegación del drill-down de la Cola de revisión.
 *
 * Muestra "Materias › Materia › Comisión › Examen" en su PROPIA fila, encima del
 * contenido del nivel. Los segmentos anteriores al actual son clickables y, al
 * activarse, recortan el path al nivel correspondiente (vía onNavigate). El último
 * segmento (nivel actual) no es clickable. Layout flex con gaps, sin posiciones
 * absolutas: nunca se monta sobre el contenido.
 */
import { Icon } from '../../ui/components';

/** Path de drill-down: ausencia de un campo = no se bajó a ese nivel todavía. */
export interface ColaPath {
  materia?: string;
  comision?: string;
  examen?: string;
}

/** Nivel al que se navega al hacer click en un segmento del breadcrumb. */
export type ColaNivel = 'raiz' | 'materia' | 'comision';

function Segmento({
  texto,
  activo,
  onClick,
}: {
  texto: string;
  activo: boolean;
  onClick?: () => void;
}) {
  if (activo || !onClick) {
    return (
      <span className="text-label-md font-semibold text-on-surface truncate max-w-[14rem]">
        {texto}
      </span>
    );
  }
  return (
    <button
      type="button"
      onClick={onClick}
      className="text-label-md text-primary hover:underline focus:outline-none
        focus-visible:ring-2 focus-visible:ring-primary/40 rounded truncate max-w-[12rem]"
    >
      {texto}
    </button>
  );
}

function Chevron() {
  return <Icon name="chevron_right" className="text-[18px] text-on-surface-variant shrink-0" />;
}

export function ColaBreadcrumb({
  path,
  onNavigate,
}: {
  path: ColaPath;
  onNavigate: (nivel: ColaNivel) => void;
}) {
  const enRaiz = !path.materia;

  return (
    <nav
      aria-label="Ruta de navegación de la cola"
      className="flex items-center flex-wrap gap-base rounded-xl bg-surface-container-low
        border border-outline-variant/40 px-md py-sm"
    >
      <Icon name="account_tree" className="text-[18px] text-on-surface-variant shrink-0" />
      <Segmento texto="Materias" activo={enRaiz} onClick={() => onNavigate('raiz')} />

      {path.materia && (
        <>
          <Chevron />
          <Segmento
            texto={path.materia}
            activo={!path.comision}
            onClick={() => onNavigate('materia')}
          />
        </>
      )}

      {path.comision && (
        <>
          <Chevron />
          <Segmento
            texto={path.comision}
            activo={!path.examen}
            onClick={() => onNavigate('comision')}
          />
        </>
      )}

      {path.examen && (
        <>
          <Chevron />
          <Segmento texto={path.examen} activo onClick={undefined} />
        </>
      )}
    </nav>
  );
}

export default ColaBreadcrumb;
