/**
 * ColaNivelPersonas — Nivel hoja del drill-down: las personas (sesiones de proctoring)
 * en riesgo de un examen puntual. Cada card = una persona, con score / señales /
 * diferencias y un botón para seleccionarla. La persona seleccionada despliega el
 * panel de decisión (ColaPanelDecision) debajo de su card.
 *
 * Layout: stack vertical con gaps (space-y-sm); las métricas usan flex-wrap. Sin
 * elementos absolutos: nada se monta sobre el texto a 1440/1280/1024px.
 */
import { Card, Badge, Icon, SectionTitle } from '../../ui/components';
import type { DecisionRevisor } from '../../lib/types';
import { formatFechaRelativa } from './helpers';
import type { SesionEnriquecida } from './colaAgregacion';
import { ColaPanelDecision } from './ColaPanelDecision';

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
      className={`w-full text-left p-md rounded-xl border transition-all focus:outline-none
        focus-visible:ring-2 focus-visible:ring-primary/40 ${
          seleccionada
            ? 'bg-primary-fixed/40 border-primary-container'
            : 'border-outline-variant/40 hover:bg-surface-container-low'
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
          {sesion.total_eventos} señales
        </span>
        <span
          className={`inline-flex items-center gap-base ${
            sesion.total_discrepancias > 0 ? 'text-error' : ''
          }`}
        >
          <Icon name="difference" className="text-[15px]" />
          {sesion.total_discrepancias} diferencias
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
  onResolver,
  onVerDetalle,
}: {
  personas: SesionEnriquecida[];
  selId: string | null;
  onSeleccionar: (id: string) => void;
  onResolver: (id: string, decision: DecisionRevisor) => void;
  onVerDetalle: (id: string) => void;
}) {
  const seleccionada = personas.find((p) => p.sesion.id === selId) ?? null;

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
        <div className="grid lg:grid-cols-2 gap-lg items-start">
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

          <div>
            {seleccionada ? (
              <ColaPanelDecision
                sesion={seleccionada.sesion}
                info={seleccionada.info}
                onResolver={(d) => onResolver(seleccionada.sesion.id, d)}
                onVerDetalle={() => onVerDetalle(seleccionada.sesion.id)}
              />
            ) : (
              <Card className="text-center py-xl space-y-base text-on-surface-variant">
                <Icon name="touch_app" className="text-[40px]" />
                <p className="text-label-md">
                  Seleccioná una persona de la lista para ver su detalle y decidir.
                </p>
              </Card>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

export default ColaNivelPersonas;
