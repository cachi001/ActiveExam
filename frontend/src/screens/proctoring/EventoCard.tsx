/**
 * EventoCard — Tarjeta de un evento de proctoring en el detalle de la sesión.
 *
 * Presenta TODO lo que el revisor necesita: tipo + severidad, timestamp, captura
 * (miniatura clickable o placeholder), veredicto de re-inferencia server-side
 * (cliente = sensor no confiable), face_count cliente vs servidor lado a lado,
 * hash corto y payload relevante. Borde-izquierdo de color según la severidad.
 */
import { Icon, SeverityBadge, Badge } from '../../ui/components';
import { HelpButton } from '../../ui/HelpButton';
import { TIPO_EVENTO_LABEL } from '../../lib/api';
import type { EventoProctoringDetalle, Severidad, TipoEvento } from '../../lib/types';
import {
  formatFecha,
  formatPayloadKey,
  formatPayloadValue,
  verdictClasses,
  verdictIcon,
  verdictLabel,
  tieneVeredicto,
  humanizarLabel,
} from './helpers';
import { ScreenshotMiniatura } from './ScreenshotMiniatura';
import { formatRostrosConOrigen } from '../../lib/faceCountLabel';

/**
 * Convierte el payload en pares legibles para revisión humana:
 * - omite claves vacías o ya representadas arriba (face_count*: se muestran como "Rostros")
 * - traduce claves a etiquetas humanas (sostenido_ms → "Duración")
 * - formatea valores: ms → "3 s" / "1 min 5 s", booleanos → "Sí/No", floats → 2 decimales.
 */
const KEYS_OCULTAS = new Set(['face_count', 'face_count_cliente', 'face_count_servidor', 'trigger_evidence', 'origen']);

function payloadEntries(payload: Record<string, unknown> | undefined): [string, string][] {
  if (!payload) return [];
  return Object.entries(payload)
    .filter(([k, v]) => v !== null && v !== undefined && v !== '' && !KEYS_OCULTAS.has(k))
    .map(([k, v]) => [formatPayloadKey(k), formatPayloadValue(k, v)] as [string, string]);
}

export function EventoCard({ evento }: { evento: EventoProctoringDetalle }) {
  const tipoLabel = TIPO_EVENTO_LABEL[evento.tipo as TipoEvento] ?? humanizarLabel(evento.tipo);
  const fcCliente = evento.face_count_cliente ?? null;
  const fcServidor = evento.face_count_servidor ?? null;
  const discrepanciaFC = fcCliente !== null && fcServidor !== null && fcCliente !== fcServidor;
  // C-72 sección 9: el bloque de conteo cliente/servidor solo aporta señal cuando
  // NO coinciden (el cliente pudo mentir, regla #6) Y hay captura para inspeccionar
  // la discrepancia. Coinciden o sin imagen → ruido, se oculta. El evento NO se oculta.
  const hayCaptura = !!evento.screenshot_base64;
  const mostrarConteo = discrepanciaFC && hayCaptura;
  const sha = evento.screenshot_sha256;
  const payload = payloadEntries(evento.payload);

  return (
    <div
      className="rounded-xl bg-surface-container-lowest p-md shadow-card animate-in fade-in"
    >
      {/* Header: tipo + severidad + timestamp */}
      <div className="flex items-start justify-between gap-sm flex-wrap">
        <div className="flex items-center gap-sm flex-wrap">
          <span className="font-headline text-title-lg text-on-surface tracking-tight">{tipoLabel}</span>
          <SeverityBadge severidad={evento.severidad as Severidad} />
          {/* C-15: el evento ocurrió durante una pausa autorizada → NO suma al
              score (el backend ya lo excluye). Badge informativo teal para que el
              revisor sepa que está contextualizado. */}
          {evento.en_pausa_autorizada && (
            <span
              className="inline-flex items-center gap-base px-sm py-px rounded-full
                bg-teal-50 text-teal-700 border border-teal-200 text-label-sm font-semibold"
              title="Ocurrió durante una pausa autorizada — no suma al score de riesgo"
            >
              <Icon name="pause_circle" className="text-[14px]" fill />
              Pausa autorizada · no suma al score
            </span>
          )}
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
          {/* Verificación del servidor — solo si el servidor re-infirió algo (si
              no, omitimos la fila en vez de mostrar "no evaluado" con un "?"). */}
          {tieneVeredicto(evento.veredicto_reinferencia) && (
            <div className="flex items-center gap-sm flex-wrap">
              <span className="inline-flex items-center gap-base text-label-sm text-on-surface-variant">
                Verificación del servidor
                <HelpButton title="Verificación del servidor">
                  <p>
                    El cliente es un <strong>sensor no confiable</strong>: el servidor vuelve a
                    analizar la captura por su cuenta y compara con lo que reportó el navegador.
                  </p>
                  <p>
                    <strong>Coincide</strong> = el servidor confirmó lo del navegador.{' '}
                    <strong>No coincide</strong> = el conteo difirió (queda marcado para el revisor).
                  </p>
                </HelpButton>
              </span>
              <span
                className={`inline-flex items-center gap-base px-sm py-px rounded-full
                  text-label-sm font-semibold border ${verdictClasses(evento.veredicto_reinferencia)}`}
              >
                <Icon name={verdictIcon(evento.veredicto_reinferencia)} className="text-[15px]" fill />
                {verdictLabel(evento.veredicto_reinferencia)}
              </span>
            </div>
          )}

          {/* Face count cliente vs servidor — solo con discrepancia Y captura (C-72 §9) */}
          {mostrarConteo && (
            <div className="flex items-center gap-sm flex-wrap">
              <span className="text-label-sm text-on-surface-variant">Rostros detectados:</span>
              <span className="inline-flex items-center gap-base px-sm py-px rounded-lg
                bg-surface-container-low text-label-sm text-on-surface">
                <Icon name="person" className="text-[14px]" />
                {formatRostrosConOrigen('Navegador', fcCliente)}
              </span>
              <span className="inline-flex items-center gap-base px-sm py-px rounded-lg
                bg-surface-container-low text-label-sm text-on-surface">
                <Icon name="dns" className="text-[14px]" />
                {formatRostrosConOrigen('Servidor', fcServidor)}
              </span>
              {discrepanciaFC && <Badge tone="error">No coinciden</Badge>}
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
                    bg-surface-container-low text-label-sm text-on-surface-variant"
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
