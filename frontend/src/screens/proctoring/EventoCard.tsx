/**
 * EventoCard — Tarjeta de un evento de proctoring en el detalle de la sesión.
 *
 * Presenta TODO lo que el revisor necesita: tipo + severidad, timestamp, captura
 * (miniatura clickable o placeholder), veredicto de re-inferencia server-side
 * (cliente = sensor no confiable), face_count cliente vs servidor lado a lado,
 * hash corto y payload relevante. Borde-izquierdo de color según la severidad.
 */
import { Icon, SeverityBadge, Badge } from '../../ui/components';
import { TIPO_EVENTO_LABEL } from '../../lib/api';
import type { EventoProctoringDetalle, Severidad, TipoEvento } from '../../lib/types';
import {
  formatFecha,
  formatPayloadKey,
  formatPayloadValue,
  verdictClasses,
  verdictIcon,
  verdictLabel,
} from './helpers';
import { ScreenshotMiniatura } from './ScreenshotMiniatura';
import { formatRostrosConOrigen } from '../../lib/faceCountLabel';

/** Borde-izquierdo de acento según severidad. */
function severidadAccent(sev: string): string {
  if (sev === 'critica') return 'border-l-error';
  if (sev === 'alta') return 'border-l-error';
  if (sev === 'media') return 'border-l-warning';
  if (sev === 'baja') return 'border-l-success';
  return 'border-l-outline-variant';
}

/**
 * Convierte el payload en pares legibles para revisión humana:
 * - omite claves vacías o ya representadas arriba (face_count*: se muestran como "Rostros")
 * - traduce claves a etiquetas humanas (sostenido_ms → "Duración")
 * - formatea valores: ms → "3 s" / "1 min 5 s", booleanos → "Sí/No", floats → 2 decimales.
 */
const KEYS_OCULTAS = new Set(['face_count', 'face_count_cliente', 'face_count_servidor', 'trigger_evidence']);

function payloadEntries(payload: Record<string, unknown> | undefined): [string, string][] {
  if (!payload) return [];
  return Object.entries(payload)
    .filter(([k, v]) => v !== null && v !== undefined && v !== '' && !KEYS_OCULTAS.has(k))
    .map(([k, v]) => [formatPayloadKey(k), formatPayloadValue(k, v)] as [string, string]);
}

export function EventoCard({ evento }: { evento: EventoProctoringDetalle }) {
  const tipoLabel = TIPO_EVENTO_LABEL[evento.tipo as TipoEvento] ?? evento.tipo;
  const fcCliente = evento.face_count_cliente ?? null;
  const fcServidor = evento.face_count_servidor ?? null;
  const hayFaceCount = fcCliente !== null || fcServidor !== null;
  const discrepanciaFC = fcCliente !== null && fcServidor !== null && fcCliente !== fcServidor;
  const sha = evento.screenshot_sha256;
  const payload = payloadEntries(evento.payload);

  return (
    <div
      className={`rounded-xl bg-surface-container-lowest border border-outline-variant/50
        border-l-4 ${severidadAccent(evento.severidad)} p-md shadow-card
        animate-in fade-in`}
    >
      {/* Header: tipo + severidad + timestamp */}
      <div className="flex items-start justify-between gap-sm flex-wrap">
        <div className="flex items-center gap-sm flex-wrap">
          <span className="font-headline text-title-lg text-on-surface tracking-tight">{tipoLabel}</span>
          <SeverityBadge severidad={evento.severidad as Severidad} />
        </div>
        <span className="inline-flex items-center gap-base text-label-sm text-on-surface-variant font-mono">
          <Icon name="schedule" className="text-[15px]" />
          {formatFecha(evento.ts_cliente, true)}
        </span>
      </div>

      <div className="grid sm:grid-cols-[120px_1fr] gap-md mt-sm">
        {/* Captura */}
        <ScreenshotMiniatura base64={evento.screenshot_base64} />

        {/* Datos del servidor + cliente */}
        <div className="space-y-sm min-w-0">
          {/* Veredicto re-inferencia */}
          <div className="flex items-center gap-sm flex-wrap">
            <span className="text-label-sm text-on-surface-variant">Re-inferencia servidor:</span>
            <span
              className={`inline-flex items-center gap-base px-sm py-px rounded-full
                text-label-sm font-semibold border ${verdictClasses(evento.veredicto_reinferencia)}`}
            >
              <Icon name={verdictIcon(evento.veredicto_reinferencia)} className="text-[15px]" fill />
              {verdictLabel(evento.veredicto_reinferencia)}
            </span>
          </div>

          {/* Face count cliente vs servidor */}
          {hayFaceCount && (
            <div className="flex items-center gap-sm flex-wrap">
              <span className="text-label-sm text-on-surface-variant">Rostros:</span>
              <span className="inline-flex items-center gap-base px-sm py-px rounded-lg
                bg-surface-container text-label-sm text-on-surface">
                <Icon name="person" className="text-[14px]" />
                {formatRostrosConOrigen('Cliente', fcCliente)}
              </span>
              <span className="inline-flex items-center gap-base px-sm py-px rounded-lg
                bg-surface-container text-label-sm text-on-surface">
                <Icon name="dns" className="text-[14px]" />
                {formatRostrosConOrigen('Servidor', fcServidor)}
              </span>
              {discrepanciaFC && <Badge tone="error">Discrepancia</Badge>}
            </div>
          )}

          {/* SHA-256 */}
          {sha && (
            <div className="flex items-center gap-base text-label-sm text-on-surface-variant" title={sha}>
              <Icon name="tag" className="text-[14px]" />
              <span className="font-mono truncate">{sha.slice(0, 16)}…</span>
            </div>
          )}

          {/* Payload relevante (claves traducidas + valores normalizados) */}
          {payload.length > 0 && (
            <div className="flex flex-wrap gap-base pt-base">
              {payload.map(([k, v]) => (
                <span
                  key={k}
                  className="inline-flex items-center gap-base px-sm py-px rounded-full
                    bg-surface-container-high text-label-sm text-on-surface-variant"
                >
                  <span className="text-on-surface-variant">{k}:</span>
                  <span className="text-on-surface font-semibold">{v}</span>
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default EventoCard;
