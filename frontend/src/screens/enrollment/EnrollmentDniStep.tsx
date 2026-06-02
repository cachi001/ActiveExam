/**
 * Paso opcional de escaneo de DNI en el enrollment del perfil (C-22, C-38, C-39).
 *
 * Captura FRENTE + DORSO reutilizando el componente compartido CameraSnapshotCapture
 * (marco escáner rectangular ID-1, cámara trasera en móvil). Opcional: su ausencia
 * NO bloquea el perfil completo.
 *
 * Fases (C-39):
 *   'inicio'     → UI de captura con botones
 *   'analizando' → spinner "Verificando documento…" durante api.analizarDNI()
 *   'resultado'  → panel con checks, OCR, concordancia, estado L2.5 y disclaimer
 *   'completado' → estado legado (sin análisis previo), re-entra en 'resultado' si existe
 *
 * DATO SENSIBLE (Ley 25.326):
 * Server-side: cifrado AES-256-GCM, finalidad acotada a verificación de identidad,
 * eliminado al egreso del estudiante, holds legales difieren la eliminación.
 *
 * Spec: optional-dni-scan (C-22) + dni-scanner-dual-side (C-38) + dni-analysis-panel (C-39)
 */
import { useState } from 'react';
import { Icon, Button, Card, Badge } from '../../ui/components';
import { CameraSnapshotCapture } from '../../ui/CameraSnapshotCapture';
import { api, ENABLE_DNI_SCAN } from '../../lib/api';
import type { EscaneDNI, AnalisisDNI } from '../../lib/types';

interface Props {
  escanActual: EscaneDNI | null;
  onEscaneado: (escan: EscaneDNI) => void;
  onOmitir: () => void;
}

type Fase = 'inicio' | 'analizando' | 'resultado' | 'completado';

/** Aspecto de la tarjeta ID-1 (DNI argentino): 85.6 × 54 mm. */
const DNI_ASPECT = 85.6 / 54;

/** Determina la fase inicial según el estado del escaneo guardado. */
function fasePorEscan(escan: EscaneDNI | null): Fase {
  if (!escan?.captura_completada) return 'inicio';
  if (escan.analisis) return 'resultado';
  return 'completado';
}

export function EnrollmentDniStep({ escanActual, onEscaneado, onOmitir }: Props) {
  const [fase, setFase] = useState<Fase>(fasePorEscan(escanActual));
  // Análisis indicativo del DNI — null hasta que api.analizarDNI() completa.
  const [analisis, setAnalisis] = useState<AnalisisDNI | null>(
    escanActual?.analisis ?? null,
  );
  // Escaneo guardado en la sesión (frente + dorso + metadatos, sin análisis todavía)
  const [escanGuardado, setEscanGuardado] = useState<EscaneDNI | null>(escanActual);

  // Lado activo de la captura ('frente' | 'dorso'); null = overlay cerrado.
  const [lado, setLado] = useState<'frente' | 'dorso' | null>(null);
  const [imagenFrente, setImagenFrente] = useState<string | null>(null);

  const handleFrenteCapturado = (dataUrl: string) => {
    setImagenFrente(dataUrl);
    setLado('dorso'); // key={lado} re-monta CameraSnapshotCapture para el dorso
  };

  const handleDorsoCapturado = async (dataUrl: string) => {
    setLado(null);
    // 1. Guardar el escaneo (frente + dorso)
    const escan = await api.guardarEscaneDNI(imagenFrente ?? '', dataUrl);
    setEscanGuardado(escan);
    // 2. Cambiar a fase 'analizando' e iniciar el análisis indicativo
    setFase('analizando');
    const resultado = await api.analizarDNI();
    setAnalisis(resultado);
    // 3. Mostrar el panel de resultados
    setFase('resultado');
  };

  // Cierra el overlay sin perder el frente ya capturado.
  const handleCancelarCaptura = () => setLado(null);

  // Botón "Continuar" en fase 'resultado': pasa el escaneo completo con análisis adjunto.
  const handleContinuarConResultado = () => {
    if (escanGuardado && analisis) {
      onEscaneado({ ...escanGuardado, analisis });
    }
  };

  const formatearFecha = (iso: string) =>
    new Date(iso).toLocaleDateString('es-AR', { day: '2-digit', month: 'long', year: 'numeric' });

  // ───────────────────────────────────────────────────────────────────────────
  // Render helpers
  // ───────────────────────────────────────────────────────────────────────────

  /** Ícono de check: check_circle (success) o warning (advertencia). */
  function CheckIcon({ ok }: { ok: boolean }) {
    return ok
      ? <Icon name="check_circle" className="text-[18px] text-success" fill />
      : <Icon name="warning" className="text-[18px] text-warning" />;
  }

  /** Panel de resultados del análisis indicativo (C-39). */
  function PanelResultado({ resultado }: { resultado: AnalisisDNI }) {
    const pct = Math.round(resultado.concordancia_facial * 100);
    const { datos_extraidos: d } = resultado;

    return (
      <div className="space-y-lg">
        {/* Sección 1: Checks de integridad documental */}
        <div className="space-y-sm">
          <p className="text-label-sm font-semibold text-on-surface-variant uppercase tracking-wide">
            Integridad del documento
          </p>
          <div className="grid grid-cols-2 gap-sm">
            <div className="flex items-center gap-xs">
              <CheckIcon ok={resultado.documento_detectado} />
              <span className="text-label-sm text-on-surface">Documento detectado</span>
            </div>
            <div className="flex items-center gap-xs">
              <CheckIcon ok={resultado.imagen_legible} />
              <span className="text-label-sm text-on-surface">Imagen legible</span>
            </div>
            <div className="flex items-center gap-xs">
              <CheckIcon ok={resultado.tipo_documento === 'dni_argentino'} />
              <span className="text-label-sm text-on-surface">Tipo: DNI Argentino</span>
            </div>
            <div className="flex items-center gap-xs">
              <CheckIcon ok={resultado.pdf417_leido} />
              <span className="text-label-sm text-on-surface">Código de barras (PDF417)</span>
            </div>
          </div>
        </div>

        {/* Sección 2: Datos OCR extraídos */}
        <div className="space-y-sm">
          <p className="text-label-sm font-semibold text-on-surface-variant uppercase tracking-wide">
            Datos extraídos por OCR
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-sm">
            <div>
              <p className="text-[10px] text-on-surface-variant uppercase tracking-wide font-semibold mb-base">Nombre</p>
              <p className="text-label-md text-on-surface font-semibold">{d.nombre}</p>
            </div>
            <div>
              <p className="text-[10px] text-on-surface-variant uppercase tracking-wide font-semibold mb-base">Apellido</p>
              <p className="text-label-md text-on-surface font-semibold">{d.apellido}</p>
            </div>
            <div>
              <p className="text-[10px] text-on-surface-variant uppercase tracking-wide font-semibold mb-base">N° Documento</p>
              <p className="text-label-md text-on-surface font-semibold">{d.numero_documento}</p>
            </div>
            <div>
              <p className="text-[10px] text-on-surface-variant uppercase tracking-wide font-semibold mb-base">CUIL</p>
              <p className="text-label-md text-on-surface font-semibold">{d.cuil}</p>
            </div>
            <div>
              <p className="text-[10px] text-on-surface-variant uppercase tracking-wide font-semibold mb-base">Fecha de nacimiento</p>
              <p className="text-label-md text-on-surface font-semibold">{d.fecha_nacimiento}</p>
            </div>
            <div>
              <p className="text-[10px] text-on-surface-variant uppercase tracking-wide font-semibold mb-base">Vencimiento</p>
              <p className="text-label-md text-on-surface font-semibold">{d.fecha_vencimiento}</p>
            </div>
          </div>
        </div>

        {/* Sección 3: Concordancia facial */}
        <div className="space-y-sm">
          <p className="text-label-sm font-semibold text-on-surface-variant uppercase tracking-wide">
            Concordancia facial
          </p>
          <div className="space-y-xs">
            <div className="flex items-center justify-between">
              <span className="text-label-sm text-on-surface-variant">
                Comparado contra tu referencia biométrica del perfil
              </span>
              <span className="text-label-md font-semibold text-on-surface">{pct}%</span>
            </div>
            {/* Barra de progreso */}
            <div className="w-full bg-surface-container-high rounded-full h-2">
              <div
                className="h-2 rounded-full bg-success"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        </div>

        {/* Sección 4: Estado general */}
        <div className="flex items-center gap-sm">
          <span className="text-label-sm text-on-surface-variant">Estado general:</span>
          <Badge
            tone={resultado.estado === 'preliminar_ok' ? 'success' : 'warning'}
            dot
          >
            {resultado.estado === 'preliminar_ok'
              ? 'Análisis preliminar — OK'
              : 'Análisis preliminar — Requiere revisión'}
          </Badge>
        </div>

        {/* Disclaimer obligatorio (L2.5) — inamovible */}
        <Card className="border-outline-variant/40">
          <div className="flex items-start gap-sm">
            <Icon name="info" className="text-[20px] text-on-surface-variant shrink-0 mt-px" />
            <div className="space-y-xs">
              <p className="text-label-sm font-semibold text-on-surface">
                Análisis indicativo
              </p>
              <p className="text-label-sm text-on-surface-variant leading-relaxed">
                Este resultado es <strong>preliminar y orientativo</strong>, generado localmente
                con fines de demostración. La validación oficial del documento (RENAPER, autenticidad
                del chip, MRZ/PDF417 completo, OCR real) se realiza <strong>server-side</strong>,
                nunca en el navegador.{' '}
                El cliente es un <strong>sensor no confiable</strong> (RN-GLB-01): los datos aquí
                mostrados no tienen valor probatorio.{' '}
                La decisión de habilitación o sanción es <strong>siempre humana</strong> — el sistema
                no aprueba ni rechaza automáticamente (L2.5).
              </p>
              <p className="text-[10px] text-on-surface-variant font-mono">
                version_analisis: {resultado.version_analisis} · {new Date(resultado.timestamp_analisis).toLocaleString('es-AR')}
              </p>
            </div>
          </div>
        </Card>

        {/* Botón Continuar */}
        <Button
          variant="secondary"
          icon="arrow_forward"
          onClick={handleContinuarConResultado}
          className="w-full"
        >
          Continuar
        </Button>
      </div>
    );
  }

  // ───────────────────────────────────────────────────────────────────────────
  // Render principal
  // ───────────────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-lg animate-in fade-in duration-400">
      {/* Encabezado */}
      <div className="flex items-center gap-sm">
        <div className="w-10 h-10 rounded-xl bg-surface-container-high text-on-surface-variant flex items-center justify-center shrink-0">
          <Icon name="badge" className="text-[20px]" />
        </div>
        <div>
          <h3 className="font-headline text-title-md text-on-surface flex items-center gap-sm">
            Verificación de identidad documental
            <span className="text-label-sm font-normal text-on-surface-variant bg-surface-container px-sm py-base rounded-full">
              Opcional
            </span>
          </h3>
          <p className="text-label-sm text-on-surface-variant">
            Escaneo de DNI (frente y dorso) · No bloquea el perfil completo
          </p>
        </div>
      </div>

      {/* Overlay inmersivo de captura (frente o dorso). key={lado} fuerza el re-montaje. */}
      {lado !== null && (
        <CameraSnapshotCapture
          key={lado}
          shape="rect"
          scannerCorners
          aspectRatio={DNI_ASPECT}
          facingMode="environment"
          jpegQuality={0.9}
          contextLabel={lado === 'frente' ? 'Paso 1 de 2 — Frente del DNI' : 'Paso 2 de 2 — Dorso del DNI'}
          instruction={
            lado === 'frente'
              ? 'Colocá el FRENTE del DNI dentro del marco y que se lea con claridad.'
              : 'Ahora dá vuelta el DNI y colocá el DORSO dentro del marco.'
          }
          onCapture={lado === 'frente' ? handleFrenteCapturado : handleDorsoCapturado}
          onCancel={handleCancelarCaptura}
        />
      )}

      {!ENABLE_DNI_SCAN ? (
        /* Flag explícitamente desactivado (VITE_ENABLE_DNI_SCAN=0) */
        <Card className="border-outline-variant/30">
          <div className="flex items-start gap-sm">
            <Icon name="upcoming" className="text-on-surface-variant text-[22px] shrink-0 mt-px" />
            <div className="space-y-xs">
              <p className="text-label-md font-semibold text-on-surface">Verificación documental — Desactivada</p>
              <p className="text-label-sm text-on-surface-variant">
                El escaneo del DNI está desactivado en esta instancia. Este paso es
                <strong> completamente opcional</strong> y su ausencia no afecta tu habilitación.
              </p>
            </div>
          </div>
          <div className="mt-md pt-md border-t border-outline-variant/40">
            <Button variant="ghost" onClick={onOmitir} icon="arrow_forward">
              Continuar sin DNI
            </Button>
          </div>
        </Card>
      ) : (
        <Card className="space-y-lg">
          {/* Fase: analizando — spinner sin botón de cancelar */}
          {fase === 'analizando' && (
            <div className="space-y-md text-center py-md">
              <div className="flex justify-center">
                <Icon name="progress_activity" className="ae-spin text-primary text-[40px]" />
              </div>
              <div>
                <p className="text-label-lg font-semibold text-on-surface">Verificando documento…</p>
                <p className="text-label-sm text-on-surface-variant mt-xs">
                  Comprobando integridad y concordancia biométrica
                </p>
              </div>
            </div>
          )}

          {/* Fase: resultado — panel completo */}
          {fase === 'resultado' && analisis && (
            <div className="space-y-md">
              <div className="flex items-center gap-sm">
                <Icon name="verified" className="text-[22px] text-success" fill />
                <p className="text-label-md font-semibold text-on-surface">Análisis del DNI completado</p>
              </div>
              <PanelResultado resultado={analisis} />
            </div>
          )}

          {/* Fase: completado (legado — sin análisis) */}
          {fase === 'completado' && escanGuardado && !analisis && (
            <div className="space-y-md">
              <div className="flex items-center gap-sm text-success">
                <Icon name="verified" className="text-[22px]" fill />
                <p className="text-label-md font-semibold text-on-surface">DNI registrado (frente y dorso)</p>
              </div>
              <p className="text-label-sm text-on-surface-variant">
                Capturado el {formatearFecha(escanGuardado.fecha_captura)}.
                Tratado como dato sensible (Ley 25.326): cifrado, finalidad acotada,
                eliminado al egreso.
              </p>
              <Button variant="ghost" onClick={onOmitir} icon="arrow_forward" className="w-full">
                Continuar
              </Button>
            </div>
          )}

          {/* Fase: inicio */}
          {fase === 'inicio' && (
            <div className="space-y-md">
              <p className="text-body-md text-on-surface-variant">
                Podés escanear el <strong>frente y el dorso</strong> de tu DNI para reforzar la
                verificación de identidad. Este paso es <strong>opcional</strong> — podés omitirlo
                y completar el perfil igual.
              </p>

              {/* Nota legal prominente */}
              <div className="flex items-start gap-sm bg-surface-container-low rounded-xl p-md border border-outline-variant/30">
                <Icon name="privacy_tip" className="text-on-surface-variant text-[18px] shrink-0 mt-px" />
                <p className="text-label-sm text-on-surface-variant">
                  <strong>Dato sensible (Ley 25.326):</strong> el frente y el dorso del DNI se cifran
                  at-rest y su uso queda restringido exclusivamente a la verificación de tu identidad.
                  Se eliminan al egreso de la institución (salvo hold disciplinario vigente).
                </p>
              </div>

              {imagenFrente && (
                <p className="text-label-sm text-success inline-flex items-center gap-base">
                  <Icon name="check_circle" className="text-[16px]" fill /> Frente capturado — falta el dorso.
                </p>
              )}

              <div className="flex gap-sm flex-col sm:flex-row">
                <Button variant="secondary" icon="badge" onClick={() => setLado(imagenFrente ? 'dorso' : 'frente')}>
                  {imagenFrente ? 'Capturar dorso' : 'Escanear DNI'}
                </Button>
                <Button variant="ghost" onClick={onOmitir} icon="skip_next">
                  Omitir este paso
                </Button>
              </div>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
