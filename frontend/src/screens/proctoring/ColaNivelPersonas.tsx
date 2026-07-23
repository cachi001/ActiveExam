/**
 * ColaNivelPersonas — Nivel hoja del drill-down: las personas (sesiones de proctoring)
 * en riesgo de un examen puntual. Cada card = una persona, con score / señales /
 * diferencias. Un click ABRE EL CASO en el detalle completo: la lista es para
 * elegir a quién revisar, el expediente para decidir (la decisión es inmutable y
 * exige mirar la evidencia, cosa que un panel lateral angosto no permite).
 *
 * Layout: stack vertical con gaps (space-y-sm); las métricas usan flex-wrap. Sin
 * elementos absolutos: nada se monta sobre el texto a 1440/1280/1024px.
 */
import { Card, Badge, Icon, SectionTitle } from '../../ui/components';
import { formatFechaRelativa } from './helpers';
import type { SesionEnriquecida } from './colaAgregacion';

function PersonaCard({
  item,
  seleccionada,
  onSeleccionar,
}: {
  item: SesionEnriquecida;
  seleccionada: boolean;
  onSeleccionar: () => void;
}) {
  const { sesion } = item;
  return (
    <button
      type="button"
      onClick={onSeleccionar}
      className={`w-full text-left p-md rounded-xl border bg-white transition-all focus:outline-none
        focus-visible:ring-2 focus-visible:ring-primary/40 ${
          seleccionada
            ? 'border-primary ring-2 ring-primary/30 shadow-card-lg'
            : 'border-outline-variant/60 shadow-card hover:shadow-card-lg hover:border-outline'
        }`}
    >
      <div className="flex items-center justify-between gap-md flex-wrap">
        <span className="text-label-md font-semibold text-on-surface truncate">
          {sesion.etiqueta?.trim() || 'Persona sin etiqueta'}
        </span>
        <Badge tone="error">Riesgo {sesion.score}</Badge>
      </div>
      <div className="flex items-center flex-wrap gap-md mt-base text-label-sm text-on-surface-variant">
        <span className="inline-flex items-center gap-base">
          <Icon name="sensors" className="text-[15px]" />
          {sesion.total_eventos ?? 0} señales
        </span>
        <span
          className={`inline-flex items-center gap-base ${
            (sesion.total_discrepancias ?? 0) > 0 ? 'text-error' : ''
          }`}
        >
          <Icon name="difference" className="text-[15px]" />
          {sesion.total_discrepancias ?? 0} diferencias
        </span>
        <span className="inline-flex items-center gap-base">
          <Icon name="schedule" className="text-[15px]" />
          {formatFechaRelativa(sesion.creada_en)}
        </span>
      </div>
    </button>
  );
}

export function ColaNivelPersonas({
  personas,
  selId,
  onSeleccionar,
}: {
  personas: SesionEnriquecida[];
  /** Solo resalta la fila abierta al volver del detalle. */
  selId: string | null;
  /** Abre el caso en el expediente, donde se decide. */
  onSeleccionar: (id: string) => void;
}) {

  return (
    <section className="space-y-md">
      <SectionTitle
        sub="Cada persona en riesgo de este examen. Elegí una para revisar y decidir."
        action={
          <Badge tone="error" dot>
            {personas.length} en riesgo
          </Badge>
        }
      >
        Personas en riesgo
      </SectionTitle>

      {personas.length === 0 ? (
        <Card className="text-center py-xl space-y-base">
          <Icon name="task_alt" className="text-success text-[40px]" fill />
          <p className="text-label-md text-on-surface-variant">
            No quedan personas en riesgo en este examen.
          </p>
        </Card>
      ) : (
        <div className="space-y-sm">
          {personas.map((item) => (
            <PersonaCard
              key={item.sesion.id}
              item={item}
              seleccionada={selId === item.sesion.id}
              onSeleccionar={() => onSeleccionar(item.sesion.id)}
            />
          ))}

        </div>
      )}
    </section>
  );
}

export default ColaNivelPersonas;
