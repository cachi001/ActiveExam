/**
 * GrabadasExamenGroup — Agrupa las sesiones GRABADAS de UN examen, colapsable.
 *
 * Misma arquitectura de información que la supervisión en vivo (ExamenVivoGroup):
 * primero el examen, y dentro sus sesiones (cada una con su SesionCard). Plegable
 * para mantener manejable el historial cuando hay muchos exámenes.
 */
import { useState, type ReactNode } from 'react';
import { Icon } from '../../ui/components';
import type { ExamInfo } from './helpers';

export function GrabadasExamenGroup({
  examInfo,
  count,
  children,
}: {
  examInfo: ExamInfo | null;
  count: number;
  children: ReactNode;
}) {
  const [colapsado, setColapsado] = useState(false);

  return (
    <section className="rounded-2xl border border-outline-variant/70 bg-surface-container-lowest shadow-card overflow-hidden">
      <header className="flex items-center gap-sm p-md border-b border-outline-variant/50 bg-white">
        <button
          type="button"
          onClick={() => setColapsado((v) => !v)}
          aria-label={colapsado ? 'Mostrar sesiones' : 'Ocultar sesiones'}
          aria-expanded={!colapsado}
          className="shrink-0 inline-flex items-center justify-center w-8 h-8 rounded-md hover:bg-surface-100 text-on-surface-variant transition-colors"
        >
          <Icon
            name="expand_more"
            className={`text-[22px] leading-none transition-transform duration-300 ease-out ${colapsado ? '-rotate-90' : ''}`}
          />
        </button>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-sm">
            <Icon name="menu_book" className="text-[18px] text-on-surface-variant shrink-0" />
            <h3 className="font-headline text-title-lg text-on-surface tracking-tight truncate">
              {examInfo?.examNombre ?? 'Sin examen vinculado'}
            </h3>
          </div>
          {examInfo && (
            <p className="text-label-sm text-on-surface-variant mt-base truncate pl-[26px]">
              {examInfo.comisionNombre} · {examInfo.docente}
            </p>
          )}
        </div>

        <span className="shrink-0 inline-flex items-center gap-base text-label-sm text-on-surface-variant">
          <Icon name="video_library" className="text-[16px]" />
          {count} {count === 1 ? 'sesión' : 'sesiones'}
        </span>
      </header>

      {/* Cuerpo colapsable — animación fluida con el truco grid-rows. */}
      <div
        className={`grid transition-[grid-template-rows] duration-300 ease-out ${colapsado ? 'grid-rows-[0fr]' : 'grid-rows-[1fr]'}`}
      >
        <div className="overflow-hidden">
          <div className="p-md space-y-sm">{children}</div>
        </div>
      </div>
    </section>
  );
}

export default GrabadasExamenGroup;
