/**
 * ScreenshotMiniatura — Miniatura de la captura de un evento, con zoom en overlay.
 *
 * DATO SENSIBLE (Ley 25.326): screenshot_base64 es dato biométrico/personal.
 * NO se loguea en consola ni se persiste; se renderiza directamente. Finalidad
 * acotada a la revisión humana.
 *
 * Si no hay captura, muestra un placeholder sobrio "sin captura".
 */
import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { Icon } from '../../ui/components';

export function ScreenshotMiniatura({ base64 }: { base64: string | null | undefined }) {
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (!expanded) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setExpanded(false);
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [expanded]);

  if (!base64) {
    return (
      <div className="flex items-center gap-base h-[88px] w-[120px] rounded-lg justify-center
        bg-surface-container-high border border-dashed border-outline-variant/60
        text-on-surface-variant">
        <div className="flex flex-col items-center gap-base">
          <Icon name="image_not_supported" className="text-[22px]" />
          <span className="text-label-sm">Sin captura</span>
        </div>
      </div>
    );
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setExpanded(true)}
        className="group relative block rounded-lg overflow-hidden border border-outline-variant/50
          hover:border-primary/50 transition-colors"
        title="Click para ampliar la captura"
        aria-label="Ampliar captura del evento"
      >
        {/* DATO SENSIBLE (Ley 25.326): renderizado directo, sin log. */}
        <img
          src={base64}
          alt="Captura del evento"
          style={{ height: 88, width: 120, objectFit: 'cover', display: 'block' }}
          className="bg-inverse-surface"
        />
        <span className="absolute inset-0 flex items-center justify-center bg-black/0
          group-hover:bg-black/30 transition-colors">
          <Icon
            name="zoom_in"
            className="text-[24px] text-white opacity-0 group-hover:opacity-100 transition-opacity"
          />
        </span>
      </button>

      {expanded &&
        createPortal(
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Captura ampliada del evento"
            className="fixed inset-0 z-[110] bg-black/70 flex items-center justify-center p-md
              animate-in fade-in"
            onClick={() => setExpanded(false)}
          >
            <div
              className="relative max-w-3xl w-full animate-in zoom-in fade-in"
              onClick={(e) => e.stopPropagation()}
            >
              <img
                src={base64}
                alt="Captura ampliada del evento"
                className="w-full rounded-2xl border border-outline-variant/40 shadow-card-lg"
              />
              <button
                type="button"
                onClick={() => setExpanded(false)}
                className="absolute top-2 right-2 w-8 h-8 inline-flex items-center justify-center rounded-full
                  bg-surface-container-lowest/95 backdrop-blur border border-outline-variant/60 shadow-sm
                  text-on-surface-variant hover:text-on-surface hover:bg-surface-container transition-colors"
                aria-label="Cerrar"
              >
                <Icon name="close" className="text-[16px]" />
              </button>
            </div>
          </div>,
          document.body,
        )}
    </>
  );
}

export default ScreenshotMiniatura;
