/**
 * Panel de glosario completo — C-28.
 * Modal accesible que lista todas las entradas del GLOSSARY.
 * Sin dependencias externas de modal; solo Tailwind + estado React local.
 */
import { useEffect } from 'react';
import { GLOSSARY } from '../config/glossary';

interface GlossaryPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export function GlossaryPanel({ isOpen, onClose }: GlossaryPanelProps) {
  // Cierre con tecla Escape
  useEffect(() => {
    if (!isOpen) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    /* Overlay */
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center p-md bg-black/40 backdrop-blur-sm"
      onClick={onClose}
      aria-hidden="false"
    >
      {/* Modal */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Glosario de términos"
        className="relative w-full max-w-lg max-h-[80vh] flex flex-col bg-surface-container-lowest rounded-2xl shadow-card-lg border border-outline-variant/40 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-lg py-md border-b border-outline-variant/40 shrink-0">
          <h2 className="font-headline text-title-md text-on-surface">Glosario de términos</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Cerrar glosario"
            className="w-9 h-9 rounded-full flex items-center justify-center text-on-surface-variant hover:bg-surface-container focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <span className="material-symbols-outlined text-[20px]" aria-hidden>close</span>
          </button>
        </div>

        {/* Lista de términos */}
        <div className="overflow-y-auto px-lg py-md space-y-md">
          {Object.entries(GLOSSARY).map(([key, entry]) => (
            <div key={key} className="space-y-xs">
              <dt className="font-semibold text-label-md text-on-surface">{entry.label}</dt>
              <dd className="text-label-sm text-on-surface-variant leading-relaxed">
                {entry.definition}
                {entry.legalRef && (
                  <span className="block mt-xs text-[11px] text-on-surface-variant/60">
                    {entry.legalRef}
                  </span>
                )}
              </dd>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="px-lg py-sm border-t border-outline-variant/40 shrink-0 text-label-sm text-on-surface-variant/60">
          {Object.keys(GLOSSARY).length} términos · Activo bajo Ley 25.326
        </div>
      </div>
    </div>
  );
}
