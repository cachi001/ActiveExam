/**
 * ColaPanelDecision — Panel de decisión del revisor para una persona seleccionada
 * en el nivel hoja del drill-down. Tres acciones en palabras llanas. El sistema
 * solo prioriza y ordena; la decisión es siempre del revisor, nunca automática.
 *
 * Reusa Card/Button/Icon/SectionTitle del design system. Sin window.confirm/alert.
 * Layout en columna con gaps; los botones envuelven (flex-wrap) sin solaparse.
 */
import { Card, Button, Icon, SectionTitle } from '../../ui/components';
import type { DecisionRevisor, SesionProctoringResumen } from '../../lib/types';
import type { ExamInfo } from './helpers';
import { scoreTextColor } from './helpers';

export function ColaPanelDecision({
  sesion,
  info,
  onResolver,
  onVerDetalle,
}: {
  sesion: SesionProctoringResumen;
  info: ExamInfo | null;
  onResolver: (decision: DecisionRevisor) => void;
  onVerDetalle: () => void;
}) {
  return (
    <Card className="space-y-lg">
      <div className="flex items-start justify-between gap-md flex-wrap border-b
        border-outline-variant/40 pb-md">
        <div className="min-w-0">
          <h3 className="font-headline text-title-lg text-on-surface truncate">
            {sesion.etiqueta?.trim() || 'Persona sin etiqueta'}
          </h3>
          {info && (
            <p className="text-label-sm text-on-surface-variant mt-base">
              {info.examNombre} · {info.comisionNombre} · {info.docente}
            </p>
          )}
        </div>
        <span className={`font-headline text-headline-md font-bold ${scoreTextColor(sesion.score)}`}>
          {sesion.score}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-sm">
        <Metrica label="Señales registradas" valor={String(sesion.total_eventos)} />
        <Metrica
          label="Diferencias con el servidor"
          valor={String(sesion.total_discrepancias)}
          clase={sesion.total_discrepancias > 0 ? 'text-error' : 'text-on-surface'}
        />
      </div>

      <button
        type="button"
        onClick={onVerDetalle}
        className="inline-flex items-center gap-base text-label-md font-semibold text-primary
          hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 rounded"
      >
        Ver detalle completo
        <Icon name="arrow_forward" className="text-[18px]" />
      </button>

      <div className="border-t border-outline-variant/40 pt-md space-y-md">
        <SectionTitle sub="El sistema solo ordena por prioridad. La decisión es siempre tuya.">
          Decisión del revisor
        </SectionTitle>
        <div className="flex flex-wrap gap-sm">
          <Button variant="outline" icon="done" onClick={() => onResolver('sin_hallazgos')}>
            Sin observaciones
          </Button>
          <Button variant="secondary" icon="flag" onClick={() => onResolver('aprobado')}>
            Aprobar con nota
          </Button>
          <Button variant="danger" icon="gavel" onClick={() => onResolver('flaggeado_para_sumario')}>
            Enviar a revisión formal
          </Button>
        </div>
      </div>
    </Card>
  );
}

function Metrica({
  label,
  valor,
  clase = 'text-on-surface',
}: {
  label: string;
  valor: string;
  clase?: string;
}) {
  return (
    <div className="rounded-xl bg-surface-container-low border border-outline-variant/40 p-sm">
      <p className="text-label-sm uppercase tracking-wide text-on-surface-variant">{label}</p>
      <p className={`font-headline text-title-lg font-bold ${clase}`}>{valor}</p>
    </div>
  );
}

export default ColaPanelDecision;
