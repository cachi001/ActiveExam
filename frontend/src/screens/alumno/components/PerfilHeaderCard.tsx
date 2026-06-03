/**
 * PerfilHeaderCard — encabezado del perfil del alumno.
 *
 * Presentación pura: recibe `principal` y renderiza el avatar condicional
 * (foto circular si existe, inicial si no) y los datos personales en un grid 2×2.
 * No accede al store ni llama APIs.
 *
 * Spec: profile-header-card (C-42)
 */
import { Card } from '../../../ui/components';
import { INSTITUTION } from '../../../config/institution';
import type { Principal } from '../../../lib/types';

interface PerfilHeaderCardProps {
  principal: Principal | null;
}

export function PerfilHeaderCard({ principal }: PerfilHeaderCardProps) {
  return (
    <Card>
      {/* Fila superior: avatar + nombre + roles */}
      <div className="flex items-center gap-md mb-lg">
        {/* Avatar condicional: foto circular si existe, inicial si no */}
        {principal?.foto_perfil ? (
          <img
            src={principal.foto_perfil}
            className="w-14 h-14 rounded-full object-cover shrink-0"
            alt={`Foto de perfil de ${principal.nombre}`}
          />
        ) : (
          <div className="w-14 h-14 rounded-full bg-secondary-container text-on-secondary flex items-center justify-center font-headline text-headline-sm shrink-0">
            {principal?.nombre.charAt(0) ?? '?'}
          </div>
        )}
        <div className="min-w-0">
          <p className="text-label-lg font-semibold text-on-surface">{principal?.nombre ?? '—'}</p>
          <p className="text-label-sm text-on-surface-variant">{principal?.roles.join(', ') ?? '—'}</p>
        </div>
      </div>

      {/* Grid 2×2 de datos personales */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-md">
        <div>
          <p className="text-label-sm text-on-surface-variant uppercase tracking-wide mb-base">Legajo</p>
          <p className="text-label-md text-on-surface font-semibold">{principal?.id_institucional ?? '—'}</p>
        </div>
        <div>
          <p className="text-label-sm text-on-surface-variant uppercase tracking-wide mb-base">Email institucional</p>
          <p className="text-label-md text-on-surface font-semibold">{principal?.email ?? '—'}</p>
        </div>
        <div>
          <p className="text-label-sm text-on-surface-variant uppercase tracking-wide mb-base">Institución</p>
          <p className="text-label-md text-on-surface font-semibold">{INSTITUTION.nombreCorto}</p>
        </div>
        <div>
          <p className="text-label-sm text-on-surface-variant uppercase tracking-wide mb-base">Jurisdicción</p>
          <p className="text-label-md text-on-surface font-semibold">{principal?.jurisdiccion ?? '—'}</p>
        </div>
      </div>
    </Card>
  );
}
