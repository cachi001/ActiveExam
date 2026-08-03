/**
 * DecisionRevisorForm — el acto de decidir sobre una sesión revisada, EN UN
 * SOLO PASO (sin segunda instancia de "resolución" ni "caso abierto").
 *
 * UNA decisión, dos salidas: **Aprobar con nota** o **Anular examen**. Ambas
 * exigen MOTIVO; anular exige además seleccionar al menos una captura de
 * evidencia de la lista de eventos de la sesión — esa selección viaja
 * ESTRUCTURADA (lista de `event_id`, no texto libre) y es lo único que
 * después ve el alumno en su informe de devolución.
 */
import { useState } from 'react';
import { Button, Icon, SectionTitle, FormField } from '../../ui/components';
import type { DecisionRevisor, EventoProctoringDetalle } from '../../lib/types';
import { TIPO_EVENTO_LABEL } from '../../lib/api';
import { formatFecha, humanizarLabel } from './helpers';
import { ScreenshotMiniatura } from './ScreenshotMiniatura';

export function DecisionRevisorForm({
  puedeResolver,
  eventos,
  onResolver,
  onDecidido,
}: {
  puedeResolver: boolean;
  /** Lista de eventos de la sesión para seleccionar como evidencia. */
  eventos?: EventoProctoringDetalle[];
  onResolver: (
    decision: DecisionRevisor,
    motivo: string,
    evidenciaIds?: string[],
  ) => Promise<boolean>;
  onDecidido?: () => void;
}) {
  const [motivo, setMotivo] = useState('');
  const [motivoTouched, setMotivoTouched] = useState(false);
  const [seleccionados, setSeleccionados] = useState<Set<string>>(new Set());
  const [enviando, setEnviando] = useState(false);

  const motivoOk = motivo.trim().length > 0;
  const hayEvidencia = seleccionados.size > 0;

  const toggleEvento = (id: string) => {
    setSeleccionados((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const aprobar = async () => {
    if (!motivoOk || enviando) return;
    setEnviando(true);
    const ok = await onResolver('aprobado', motivo.trim());
    setEnviando(false);
    if (ok) onDecidido?.();
  };

  const anular = async () => {
    if (!motivoOk || !puedeResolver || enviando || !hayEvidencia) return;
    setEnviando(true);
    const ok = await onResolver('anulado', motivo.trim(), Array.from(seleccionados));
    setEnviando(false);
    if (ok) onDecidido?.();
  };

  const eventosConCaptura = (eventos ?? []).filter((ev) => ev.screenshot_base64);
  const eventosSinCaptura = (eventos ?? []).filter((ev) => !ev.screenshot_base64);

  return (
    <div className="space-y-md">
      <SectionTitle sub="El sistema solo ordena por prioridad. La decisión es siempre tuya.">
        Decisión del revisor
      </SectionTitle>

      <FormField
        label="Motivo (obligatorio)"
        hint="Fundamento de la decisión. Queda en el registro inmutable de auditoría."
        error={motivoTouched && !motivoOk ? 'Escribí un motivo para poder registrar la decisión.' : undefined}
      >
        <textarea
          value={motivo}
          onChange={(e) => setMotivo(e.target.value)}
          onBlur={() => setMotivoTouched(true)}
          rows={2}
          placeholder="Ej.: revisé las 3 señales y corresponden a un falso positivo."
          className="w-full rounded-xl border border-outline-variant/60 bg-white p-sm text-body-md resize-none
            focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
        />
      </FormField>

      {/* Selector de evidencia — solo visible para quienes pueden anular */}
      {puedeResolver && (eventos ?? []).length > 0 && (
        <div className="space-y-sm">
          <div className="flex items-center justify-between">
            <p className="text-label-sm font-semibold text-on-surface-variant uppercase tracking-wide">
              Capturas de evidencia
            </p>
            <p className="text-label-sm text-on-surface-variant">
              {seleccionados.size > 0
                ? `${seleccionados.size} seleccionada${seleccionados.size !== 1 ? 's' : ''}`
                : 'Seleccioná al menos una para anular'}
            </p>
          </div>

          {/* Eventos con captura — grilla de miniaturas (click amplía SIN recortar;
              el checkbox de la esquina selecciona como evidencia del veredicto). */}
          {eventosConCaptura.length > 0 && (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-sm">
              {eventosConCaptura.map((ev) => {
                const sel = seleccionados.has(ev.evento_id);
                const label = TIPO_EVENTO_LABEL[ev.tipo as keyof typeof TIPO_EVENTO_LABEL] ?? humanizarLabel(ev.tipo);
                return (
                  <div
                    key={ev.evento_id}
                    className={`relative rounded-xl border-2 overflow-hidden transition-all ${
                      sel
                        ? 'border-error ring-2 ring-error/30'
                        : 'border-outline-variant/40 hover:border-outline'
                    }`}
                  >
                    <ScreenshotMiniatura base64={ev.screenshot_base64} />
                    <div className="p-xs bg-surface-container-low space-y-xs">
                      <p className="text-label-sm font-medium text-on-surface leading-tight line-clamp-1">{label}</p>
                      <p className="text-label-xs text-on-surface-variant">{formatFecha(ev.ts_cliente, true)}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => toggleEvento(ev.evento_id)}
                      aria-pressed={sel}
                      aria-label={sel ? 'Quitar de la evidencia' : 'Elegir como evidencia'}
                      className={`absolute top-xs right-xs rounded-full w-6 h-6 flex items-center justify-center transition-colors ${
                        sel
                          ? 'bg-error text-on-error'
                          : 'bg-surface-container-lowest/90 text-on-surface-variant border border-outline-variant/60'
                      }`}
                    >
                      <Icon name={sel ? 'check' : 'add'} className="text-[14px]" />
                    </button>
                  </div>
                );
              })}
            </div>
          )}

          {/* Eventos sin captura — lista compacta */}
          {eventosSinCaptura.length > 0 && (
            <div className="space-y-xs">
              {eventosSinCaptura.map((ev) => {
                const sel = seleccionados.has(ev.evento_id);
                const label = TIPO_EVENTO_LABEL[ev.tipo as keyof typeof TIPO_EVENTO_LABEL] ?? humanizarLabel(ev.tipo);
                return (
                  <label
                    key={ev.evento_id}
                    className={`flex items-center gap-sm px-sm py-xs rounded-lg border cursor-pointer transition-all ${
                      sel
                        ? 'border-error/50 bg-error-container/30'
                        : 'border-outline-variant/40 hover:bg-surface-container-low'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={sel}
                      onChange={() => toggleEvento(ev.evento_id)}
                      className="accent-error w-4 h-4 shrink-0"
                    />
                    <Icon name="warning" className="text-[16px] text-warning shrink-0" fill />
                    <span className="text-label-sm text-on-surface flex-1">{label}</span>
                    <span className="text-label-xs text-on-surface-variant whitespace-nowrap">{formatFecha(ev.ts_cliente, true)}</span>
                  </label>
                );
              })}
            </div>
          )}
        </div>
      )}

      <div className="grid gap-sm sm:grid-cols-2">
        <Button
          variant="success"
          icon="verified"
          disabled={!motivoOk || enviando}
          onClick={aprobar}
          className="justify-center"
        >
          Aprobar con nota
        </Button>
        {puedeResolver && (
          <Button
            variant="danger"
            icon="gavel"
            disabled={!motivoOk || enviando || !hayEvidencia}
            onClick={anular}
            className="justify-center font-bold"
          >
            Anular examen
          </Button>
        )}
      </div>

      {!puedeResolver && (
        <p className="text-label-sm text-on-surface-variant inline-flex items-center gap-base">
          <Icon name="lock" className="text-[16px]" />
          No tenés la atribución para anular. Podés aprobar la nota.
        </p>
      )}
    </div>
  );
}
