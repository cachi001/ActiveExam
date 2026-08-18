/**
 * EventoCard — Tarjeta de un evento de proctoring en el detalle de la sesión.
 *
 * Presenta TODO lo que el revisor necesita: tipo + severidad, timestamp, captura
 * (miniatura clickable o placeholder), veredicto de re-inferencia server-side
 * (cliente = sensor no confiable), face_count cliente vs servidor lado a lado,
 * hash corto y payload relevante. Borde-izquierdo de color según la severidad.
 */
import { Icon, SeverityBadge } from '../../ui/components';
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

/**
 * C-76 (15.5): eventos cuya captura es CONTEXTO VISUAL, no prueba del evento —
 * a diferencia de `multiples_rostros`/`rostro_ausente`, donde el servidor re-infiere
 * la MISMA imagen. Acá el screenshot solo ayuda al revisor a juzgar la situación;
 * el registro del evento (tipo + timestamp, y en `copiar_pegar` el hash) ya es la
 * evidencia real. Mostrar la leyenda evita que se lea como confirmación automática.
 */
const EVENTOS_CAPTURA_CONTEXTUAL = new Set(['cambio_pestana', 'copiar_pegar']);

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
  // El conteo cliente/servidor es precisamente el "por qué" de un veredicto "no
  // coincide": se muestra siempre que haya discrepancia, CON o SIN captura (antes
  // se ocultaba sin captura y el revisor veía "no coincide" sin ninguna pista de
  // qué difirió).
  const mostrarConteo = discrepanciaFC;
  const sha = evento.screenshot_sha256;
  const payload = payloadEntries(evento.payload);
  // C-76 (15.5): leyenda "contexto, no prueba del evento" — solo cuando hay
  // captura Y el tipo es de los que NO se re-infieren server-side.
  const esCapturaContextual = EVENTOS_CAPTURA_CONTEXTUAL.has(evento.tipo) && !!evento.screenshot_base64;

  return (
    <div className="rounded-xl bg-surface-container-lowest p-md shadow-card animate-in fade-in flex flex-col gap-sm h-full">
      {/* Header: tipo + severidad + timestamp */}
      <div className="flex items-start justify-between gap-sm flex-wrap pb-sm border-b border-outline-variant/30">
        <div className="flex items-center gap-sm flex-wrap">
          <span className="font-headline text-title-lg text-on-surface tracking-tight">{tipoLabel}</span>
          <SeverityBadge severidad={evento.severidad as Severidad} />
        </div>
        <span className="inline-flex items-center gap-base text-label-sm text-on-surface-variant font-mono">
          <Icon name="schedule" className="text-[15px]" />
          {formatFecha(evento.ts_cliente, true)}
        </span>
      </div>

      {/* C-15: el evento ocurrió durante una pausa autorizada → NO suma al score
          (el backend ya lo excluye). Badge informativo para que el revisor sepa
          que está contextualizado. */}
      {evento.en_pausa_autorizada && (
        <span
          className="self-start inline-flex items-center gap-base px-sm py-px rounded-full
            bg-teal-50 text-teal-700 border border-teal-200 text-label-sm font-semibold"
          title="Ocurrió durante una pausa autorizada — no suma al score de riesgo"
        >
          <Icon name="pause_circle" className="text-[14px]" fill />
          Pausa autorizada · no suma al score
        </span>
      )}

      {/* Captura centrada arriba; todo lo demás (verificación, payload, hash)
          apilado debajo, a todo el ancho — sin caja/card propia, para que se
          integre con el fondo gris de la tarjeta en vez de quedar como un
          bloque separado dentro de otro bloque. */}
      <div className="flex flex-col items-center gap-xs">
        <ScreenshotMiniatura base64={evento.screenshot_base64} />
        {esCapturaContextual && (
          <span
            className="inline-flex items-center gap-base px-sm py-px rounded-full
              bg-surface-container-low text-on-surface-variant text-label-sm text-center"
            title="La captura es contexto para el revisor; el evento no se re-verifica sobre la imagen."
          >
            <Icon name="info" className="text-[14px]" />
            Contexto para revisión, no prueba automática del evento
          </span>
        )}
      </div>

      <div className="space-y-sm">
        {/* Verificación del servidor — solo si el servidor re-infirió algo, O
            si hay discrepancia de conteo (el "por qué"), aunque no haya
            veredicto explícito. Es el dato de mayor autoridad (cliente =
            sensor no confiable), separado del resto con una línea, no una caja. */}
        {(tieneVeredicto(evento.veredicto_reinferencia) || mostrarConteo) && (
          <div className="space-y-xs pt-sm border-t border-outline-variant/30">
            {tieneVeredicto(evento.veredicto_reinferencia) && (
              <span className="inline-flex items-center gap-base text-label-sm font-semibold text-on-surface">
                <Icon name="verified_user" className="text-[15px]" />
                Verificación del servidor
              </span>
            )}
            {/* Face count cliente vs servidor — la comparación, el "por qué".
                Va ANTES del veredicto: primero los números crudos, después la
                conclusión ("no coincide") que se lee de esos números. */}
            {mostrarConteo && (
              <div className="flex items-center gap-sm flex-wrap">
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
              </div>
            )}
            {/* Veredicto — la conclusión, AL FINAL, después de mostrar en qué se basa. */}
            {tieneVeredicto(evento.veredicto_reinferencia) && (
              <span
                className={`inline-flex items-center gap-base px-sm py-px rounded-full
                  text-label-sm font-semibold border ${verdictClasses(evento.veredicto_reinferencia)}`}
              >
                <Icon name={verdictIcon(evento.veredicto_reinferencia)} className="text-[15px]" fill />
                {verdictLabel(evento.veredicto_reinferencia)}
              </span>
            )}
          </div>
        )}

        {/* Payload relevante (claves traducidas + valores normalizados) */}
        {payload.length > 0 && (
          <div className="flex flex-wrap gap-base">
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

        {/* SHA-256 */}
        {sha && (
          <div className="flex items-center gap-base text-label-sm text-on-surface-variant" title={sha}>
            <Icon name="tag" className="text-[14px]" />
            <span className="font-mono truncate">{sha.slice(0, 16)}…</span>
          </div>
        )}
      </div>
    </div>
  );
}

export default EventoCard;
