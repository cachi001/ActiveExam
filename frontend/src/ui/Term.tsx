/**
 * Componente átomo <Term> — C-28.
 * Envuelve terminología técnica con un tooltip accesible.
 * Hover en desktop (CSS puro Tailwind), tap en mobile (estado local).
 * Sin dependencias externas de tooltip.
 */
import { useRef, useState, useEffect, useId } from 'react';
import type { ReactNode } from 'react';
import { GLOSSARY } from '../config/glossary';
import type { TermKey } from '../config/glossary';

export interface TermProps {
  /** Clave del término en GLOSSARY */
  termKey: TermKey;
  /** Texto visible. Si se omite, usa GLOSSARY[termKey].label */
  children?: ReactNode;
  className?: string;
}

export function Term({ termKey, children, className = '' }: TermProps) {
  const entry = GLOSSARY[termKey];
  const [isTipVisible, setIsTipVisible] = useState(false);
  const wrapperRef = useRef<HTMLSpanElement>(null);
  // Genera un id único por instancia para aria-describedby
  const baseId = useId();
  const tooltipId = `term-tooltip-${baseId}`;

  // Cierre del tooltip al click fuera (touch/mobile)
  useEffect(() => {
    if (!isTipVisible) return;
    function handleClickOutside(event: MouseEvent | TouchEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setIsTipVisible(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('touchstart', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('touchstart', handleClickOutside);
    };
  }, [isTipVisible]);

  function handleClick(e: React.MouseEvent | React.TouchEvent) {
    e.stopPropagation();
    setIsTipVisible((v) => !v);
  }

  return (
    <span
      ref={wrapperRef}
      className={`relative inline-flex items-baseline gap-[2px] group ${className}`}
    >
      {/* Texto técnico con subrayado punteado */}
      <span
        className="underline decoration-dotted underline-offset-2 cursor-help"
        aria-describedby={tooltipId}
      >
        {children ?? entry.label}
      </span>

      {/* Icono "?" */}
      <button
        type="button"
        tabIndex={0}
        aria-label={`Ver definición de ${entry.label}`}
        onClick={handleClick}
        className="text-[10px] font-bold text-primary bg-primary/10 hover:bg-primary/20 w-4 h-4 rounded-full inline-flex items-center justify-center leading-none shrink-0 translate-y-[1px] focus:outline-none focus:ring-1 focus:ring-primary"
      >
        ?
      </button>

      {/* Tooltip */}
      <span
        id={tooltipId}
        role="tooltip"
        className={`
          absolute bottom-full left-0 z-50 mb-1
          w-64 max-w-[90vw]
          bg-inverse-surface text-inverse-on-surface
          text-label-sm leading-snug
          px-sm py-sm rounded-xl shadow-card-lg
          pointer-events-none
          transition-all duration-150
          ${isTipVisible
            ? 'opacity-100 visible'
            : 'opacity-0 invisible group-hover:opacity-100 group-hover:visible'
          }
        `}
      >
        <span className="block font-semibold mb-[2px]">{entry.label}</span>
        <span className="block">{entry.definition}</span>
        {entry.legalRef && (
          <span className="block mt-[4px] text-[10px] opacity-70">{entry.legalRef}</span>
        )}
      </span>
    </span>
  );
}
