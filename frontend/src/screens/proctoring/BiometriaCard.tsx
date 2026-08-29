/**
 * BiometriaCard — Sección de verificación biométrica del detalle de sesión.
 *
 * Muestra el resultado de liveness, los retos resueltos (como chips) y el
 * estado general. Diseño moderno con información siempre visible.
 */
import { Icon, Card, SectionTitle } from '../../ui/components';
import type { BiometriaDetalle } from '../../lib/types';
import { nombreDelReto } from '../../vision/liveness';

// Este archivo tenía su propio mapa de etiquetas con las claves EQUIVOCADAS
// (`parpadeo`, `giro_cabeza`, `sonrisa`), mientras que los ids que la captura
// guarda de verdad son `parpadear`, `girar_cabeza` y `sonreír`. Como ninguna
// coincidía, el `?? reto` de reserva se activaba siempre y en pantalla se leía el
// identificador crudo, con guion bajo incluido. Ahora se usa la función que vive
// junto a los retos, que es la única que conoce sus nombres.
const retoLabel = nombreDelReto;

export function BiometriaCard({ biometria }: { biometria: BiometriaDetalle | null }) {
  return (
    <Card className="space-y-md">
      <SectionTitle sub="Verificación de liveness e identidad previa al examen">
        Verificación biométrica
      </SectionTitle>

      {biometria === null ? (
        <div className="flex items-center gap-sm text-body-md text-on-surface-variant py-sm">
          <Icon name="fingerprint" className="text-[22px]" />
          Sin verificación biométrica registrada en esta sesión.
        </div>
      ) : (
        <div className="space-y-md">
          {/* Estado principal */}
          {(() => {
            const ok = biometria.resultado === 'verificado';
            const esVirtualCam = biometria.resultado === 'camara_virtual_detectada';
            const titulo = ok
              ? 'Identidad verificada'
              : esVirtualCam
                ? 'Cámara virtual detectada'
                : 'Verificación no superada';
            const icono = ok ? 'verified' : esVirtualCam ? 'videocam_off' : 'gpp_bad';
            const colorClass = ok ? 'bg-success/5 border-success/25' : 'bg-error/5 border-error/25';
            const textClass = ok ? 'text-success' : 'text-error';
            return (
              <div className={`flex items-center gap-sm p-md rounded-xl border ${colorClass}`}>
                <Icon name={icono} className={`text-[28px] shrink-0 ${textClass}`} fill />
                <div>
                  <p className={`font-semibold text-[15px] ${textClass}`}>{titulo}</p>
                  {esVirtualCam && (
                    <p className="text-[12px] text-on-surface-variant mt-0.5">
                      Se detectaron señales de cámara virtual o feed en loop durante la captura.
                    </p>
                  )}
                </div>
              </div>
            );
          })()}

          {/* Grid: liveness + retos */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-md">
            {/* Liveness pasivo */}
            <div className="rounded-xl border border-outline-variant/40 bg-surface-container-lowest p-md space-y-xs">
              {/* Decía «Liveness pasivo», pero el campo dejó de ser solo eso: ahora
                  resume las DOS fuentes de evidencia (los retos activos y las
                  señales pasivas). El nombre viejo describía la implementación y
                  encima en jerga; éste dice qué se está afirmando. */}
              <p className="text-[11px] font-semibold text-on-surface-variant uppercase tracking-wide">
                Prueba de vida
              </p>
              <div className={`flex items-center gap-xs ${biometria.liveness_ok ? 'text-success' : 'text-error'}`}>
                <Icon
                  name={biometria.liveness_ok ? 'check_circle' : 'cancel'}
                  className="text-[18px]"
                  fill
                />
                <span className="text-[13px] font-medium">
                  {biometria.liveness_ok ? 'Superado' : 'No superado'}
                </span>
              </div>
              <p className="text-[11px] text-on-surface-variant">
                Se confirma con los retos completados o con las señales de video en
                vivo (parpadeo, micro-movimientos, profundidad).
              </p>
            </div>

            {/* Retos resueltos */}
            <div className="rounded-xl border border-outline-variant/40 bg-surface-container-lowest p-md space-y-sm">
              <p className="text-[11px] font-semibold text-on-surface-variant uppercase tracking-wide">
                Retos completados ({biometria.retos_resueltos.length})
              </p>
              {biometria.retos_resueltos.length === 0 ? (
                <p className="text-[12px] text-on-surface-variant">Sin retos registrados.</p>
              ) : (
                <div className="flex flex-wrap gap-xs">
                  {biometria.retos_resueltos.map((r) => (
                    <span
                      key={r}
                      className="inline-flex items-center gap-xs px-sm py-0.5 rounded-full bg-primary-fixed/60 text-on-primary-fixed text-[11px] font-medium"
                    >
                      <Icon name="check" className="text-[12px]" />
                      {retoLabel(r)}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}

export default BiometriaCard;
