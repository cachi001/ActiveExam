/**
 * ColaNivelGrid — Grilla genérica de un nivel del drill-down (Materias, Comisiones,
 * Exámenes). Cada nodo se muestra como una card clickable con su nombre y un badge
 * "N en riesgo". Reutilizado por los tres niveles intermedios para no duplicar layout.
 *
 * Layout: grid responsive que colapsa limpio (1 col → 2 → 3) con gaps claros. El
 * badge de contador vive dentro del flujo de la card (flex), NO posicionado encima
 * del texto. Sin elementos absolutos: no hay solapamientos a 1440/1280/1024px.
 */
import { Card, Badge, Icon, SectionTitle } from '../../ui/components';
import type { NodoCola } from './colaAgregacion';

function ColaNivelCard({
  nodo,
  icono,
  onClick,
}: {
  nodo: NodoCola;
  icono: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40
        rounded-xl group"
    >
      <Card className="h-full flex flex-col gap-md transition-all
        group-hover:border-primary/40 group-hover:shadow-card-lg">
        <div className="flex items-start justify-between gap-md">
          <div className="w-11 h-11 rounded-xl bg-primary-fixed text-primary flex items-center
            justify-center shrink-0">
            <Icon name={icono} className="text-[22px]" fill />
          </div>
          <Badge tone="error" dot>
            {nodo.enRiesgo} en riesgo
          </Badge>
        </div>
        <div className="min-w-0">
          <p className="font-headline text-title-md text-on-surface leading-snug break-words">
            {nodo.nombre}
          </p>
        </div>
        <div className="mt-auto flex items-center gap-base text-label-sm text-primary
          font-semibold pt-base">
          Abrir
          <Icon name="arrow_forward" className="text-[16px]" />
        </div>
      </Card>
    </button>
  );
}

export function ColaNivelGrid({
  titulo,
  sub,
  nodos,
  icono,
  onSelect,
}: {
  titulo: string;
  sub?: string;
  nodos: NodoCola[];
  icono: string;
  onSelect: (nombre: string) => void;
}) {
  return (
    <section className="space-y-md">
      <SectionTitle sub={sub}>{titulo}</SectionTitle>

      {nodos.length === 0 ? (
        <Card className="text-center py-xl space-y-base">
          <Icon name="inbox" className="text-[40px] text-on-surface-variant" />
          <p className="text-label-md text-on-surface-variant">
            No hay elementos en riesgo en este nivel.
          </p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-md">
          {nodos.map((nodo) => (
            <ColaNivelCard
              key={nodo.clave}
              nodo={nodo}
              icono={icono}
              onClick={() => onSelect(nodo.nombre)}
            />
          ))}
        </div>
      )}
    </section>
  );
}

export default ColaNivelGrid;
