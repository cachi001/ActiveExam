/**
 * SeccionConsentimiento — publicación versionada del texto de consentimiento.
 *
 * Flujo real:
 *  1. Carga: getConsentText() (texto vigente del backend) + obtenerConfigEfectiva()
 *     (para saber qué versión está activa).
 *  2. Si el admin edita los bloques SIN cambiar la versión → bloquear guardar
 *     con un mensaje claro: debe ingresar una versión nueva.
 *  3. Con versión nueva: crearVersionConsentimiento() → editarConfigSistema()
 *     → resetEffectiveConfigCache(). Toast informando que los alumnos deben re-consentir.
 *  4. Si solo cambia la versión pero no el texto (sin sentido práctico, pero válido):
 *     igual crea la versión nueva con los bloques actuales.
 *  5. 409 (versión ya existe): mensaje claro al admin.
 */
import { useState, useEffect, useCallback } from 'react';
import { Card, Button, Icon } from '../../ui/components';
import { useToast } from '../../ui/toast';
import { api } from '../../lib/api';
import { resetEffectiveConfigCache } from '../../config/effectiveConfigCache';
import type { BloqueConsentimiento } from '../../lib/types';

export default function SeccionConsentimiento() {
  const toast = useToast();
  const [bloques, setBloques] = useState<BloqueConsentimiento[]>([]);
  const [bloquesInicial, setBloquesInicial] = useState<BloqueConsentimiento[]>([]);
  const [version, setVersion] = useState('');
  const [nuevaVersion, setNuevaVersion] = useState('');
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    // Carga el texto vigente del backend y la versión activa de la config efectiva.
    Promise.all([
      api.getConsentText(),
      api.obtenerConfigEfectiva(),
    ])
      .then(([t, cfg]) => {
        setBloques(t.bloques);
        setBloquesInicial(t.bloques);
        setVersion(cfg.consent_version_vigente);
        setNuevaVersion(cfg.consent_version_vigente);
      })
      .catch((e) => toast.error(`No se pudo cargar el consentimiento: ${e instanceof Error ? e.message : String(e)}`))
      .finally(() => setCargando(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Dirty: cambió la versión o algún bloque
  const versionCambio = nuevaVersion.trim() !== version;
  const bloquesCambiaron =
    bloques.length !== bloquesInicial.length ||
    bloques.some((b, i) => {
      const orig = bloquesInicial[i];
      return !orig || b.titulo !== orig.titulo || b.cuerpo !== orig.cuerpo;
    });
  const dirty = versionCambio || bloquesCambiaron;

  // Invariante: si editó texto pero no cambió la versión → no se puede guardar.
  const textoCambioSinVersion = bloquesCambiaron && !versionCambio;

  const cancelar = useCallback(() => {
    setBloques(bloquesInicial);
    setNuevaVersion(version);
  }, [bloquesInicial, version]);

  function setBloque(i: number, field: keyof BloqueConsentimiento, value: string) {
    setBloques((prev) => prev.map((b, idx) => (idx === i ? { ...b, [field]: value } : b)));
  }

  function agregarBloque() {
    setBloques((prev) => [...prev, { titulo: 'Nueva cláusula', cuerpo: '', icono: 'article' }]);
  }

  function eliminarBloque(i: number) {
    // Siempre debe quedar al menos una cláusula.
    setBloques((prev) => (prev.length <= 1 ? prev : prev.filter((_, idx) => idx !== i)));
  }

  // Auto-grow: ajusta el alto del textarea a su contenido (sin scroll interno que recorte).
  function autoGrow(el: HTMLTextAreaElement | null) {
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight}px`;
  }

  async function guardar() {
    const versionTrimmed = nuevaVersion.trim();

    // Validación: texto editado sin nueva versión → bloquear.
    if (textoCambioSinVersion) {
      toast.error('Cambiaste el texto: ingresá una versión nueva antes de guardar.');
      return;
    }

    if (!versionTrimmed) {
      toast.error('Ingresá un nombre de versión antes de guardar.');
      return;
    }

    setGuardando(true);
    try {
      // 1. Crear la nueva versión del texto en el backend.
      await api.crearVersionConsentimiento({
        version: versionTrimmed,
        bloques: bloques.map(({ titulo, cuerpo }) => ({ titulo, cuerpo })),
      });

      // 2. Activar la versión nueva en la config del sistema.
      await api.editarConfigSistema({ consent_version_vigente: versionTrimmed });
      resetEffectiveConfigCache();

      // 3. Confirmar localmente y notificar.
      setVersion(versionTrimmed);
      setNuevaVersion(versionTrimmed);
      setBloquesInicial(bloques);
      toast.success(`Publicaste la versión "${versionTrimmed}". Los alumnos deberán confirmar el nuevo texto antes de rendir.`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      if (msg.includes('409') || msg.includes('HTTP 409')) {
        toast.error(`La versión "${versionTrimmed}" ya existe. Ingresá un nombre de versión diferente.`);
      } else {
        toast.error(`Error al guardar: ${msg}`);
      }
    } finally {
      setGuardando(false);
    }
  }

  if (cargando) {
    return (
      <div className="space-y-lg max-w-6xl">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-[140px] rounded-2xl border border-outline-variant/40 bg-white animate-pulse" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-lg max-w-6xl">
      {/* Título de la sección */}
      <div>
        <h2 className="font-headline text-title-xl text-on-surface tracking-tight">Consentimiento</h2>
        <p className="text-[13px] text-on-surface-variant mt-1">
          Texto que los alumnos leen y confirman antes de rendir. Publicar una nueva versión obliga a todos
          los alumnos a leer y confirmar el texto actualizado.
        </p>
      </div>

      {/* Versión vigente actual */}
      <div className="flex items-start gap-3 px-4 py-3 rounded-xl bg-surface-container border border-outline-variant/60">
        <Icon name="article" className="text-[20px] text-on-surface-variant shrink-0 mt-0.5" />
        <div className="space-y-0.5">
          <p className="text-[13px] font-semibold text-on-surface">
            Versión activa: <span className="font-mono">{version}</span>
          </p>
          <p className="text-[12px] text-on-surface-variant">
            Editá el texto y publicalo con una versión nueva para que los alumnos lo confirmen.
          </p>
        </div>
      </div>

      {/* Campo de nueva versión */}
      <Card className="flex items-end gap-md">
        <div className="flex-1 space-y-base">
          <label className="text-label-sm font-semibold text-on-surface block">
            Versión a publicar
          </label>
          <p className="text-[11px] text-on-surface-variant">
            Cada versión es permanente e inmutable. Si cambiás el texto, debés publicarlo bajo
            una versión nueva (ej. v2, v1.1, 2026-06).
          </p>
          <input
            type="text"
            value={nuevaVersion}
            onChange={(e) => setNuevaVersion(e.target.value)}
            placeholder="ej. v2, v1.1, 2026-06"
            className="w-full px-sm py-base rounded-xl border border-outline-variant bg-white font-mono text-label-md focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
          />
        </div>
        {versionCambio && (
          <div className="flex items-center gap-base text-warning text-[12px] shrink-0 pb-sm">
            <Icon name="warning" className="text-[16px]" />
            Los alumnos deberán re-confirmar
          </div>
        )}
      </Card>

      {/* Alerta: texto editado sin versión nueva */}
      {textoCambioSinVersion && (
        <div className="flex items-start gap-sm px-md py-sm rounded-xl bg-error-container border border-error/30">
          <Icon name="error" className="text-error text-[18px] shrink-0 mt-px" />
          <p className="text-[12px] text-on-surface">
            <strong>Cambios de texto requieren una versión nueva.</strong>{' '}
            Ingresá un nombre de versión diferente a <span className="font-mono">"{version}"</span> para poder guardar.
          </p>
        </div>
      )}

      {bloques.map((b, i) => (
        <Card key={i} className="space-y-sm flex flex-col">
          <div className="flex items-start gap-sm">
            <input
              type="text"
              value={b.titulo}
              onChange={(e) => setBloque(i, 'titulo', e.target.value)}
              placeholder={`Título de la cláusula ${i + 1}`}
              className="flex-1 min-w-0 text-title-md font-headline text-on-surface bg-white rounded-lg border border-outline-variant px-3 py-1.5 hover:border-outline focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30 transition-colors"
              aria-label={`Título de la cláusula ${i + 1}`}
            />
            <button
              type="button"
              onClick={() => eliminarBloque(i)}
              disabled={bloques.length <= 1}
              title={bloques.length <= 1 ? 'Debe quedar al menos una cláusula' : 'Eliminar cláusula'}
              aria-label={`Eliminar cláusula ${i + 1}`}
              className="shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-error-container hover:text-error disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-on-surface-variant transition-colors"
            >
              <Icon name="delete" className="text-[18px]" />
            </button>
          </div>
          <textarea
            ref={autoGrow}
            value={b.cuerpo}
            onChange={(e) => { setBloque(i, 'cuerpo', e.target.value); autoGrow(e.target); }}
            className="w-full text-[13px] text-on-surface-variant bg-white rounded-xl border border-outline-variant p-sm min-h-[7rem] overflow-hidden resize-none focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
            aria-label={`Cuerpo de la cláusula ${i + 1}`}
          />
        </Card>
      ))}

      {/* Agregar una nueva cláusula al consentimiento */}
      <button
        type="button"
        onClick={agregarBloque}
        className="w-full flex items-center justify-center gap-sm py-3 rounded-xl border border-primary/50 bg-primary/5 text-primary hover:bg-primary/10 hover:border-primary transition-colors text-label-md font-semibold"
      >
        <Icon name="add" className="text-[18px]" />
        Agregar cláusula
      </button>

      {/* Footer dirty-aware */}
      {dirty && (
        <div className="flex items-center justify-between gap-sm pt-sm border-t border-outline-variant/40">
          <div className="flex items-center gap-xs text-[12px] text-on-surface-variant">
            <Icon name="edit" className="text-[14px]" />
            Hay cambios sin guardar
          </div>
          <div className="flex gap-sm">
            <Button variant="outline" icon="undo" onClick={cancelar} disabled={guardando}>
              Cancelar
            </Button>
            <Button
              icon="publish"
              onClick={guardar}
              disabled={guardando || textoCambioSinVersion || !nuevaVersion.trim()}
            >
              {guardando ? 'Publicando…' : 'Publicar versión'}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
