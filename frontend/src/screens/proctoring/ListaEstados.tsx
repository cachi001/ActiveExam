/**
 * Estados de la lista de sesiones: skeleton de carga y vacío.
 *
 * El skeleton imita la forma de una SesionCard (con su borde-izquierdo y filas)
 * usando el shimmer del sistema, para que la carga no parezca improvisada.
 */
import { Icon } from '../../ui/components';

function SkeletonLinea({ className = '' }: { className?: string }) {
  return (
    <div className={`relative overflow-hidden rounded-md bg-surface-container-high ${className}`}>
      <div className="absolute inset-0 shimmer" />
    </div>
  );
}

export function ListaSkeleton({ filas = 3 }: { filas?: number }) {
  return (
    <div className="space-y-sm" aria-busy="true" aria-label="Cargando sesiones">
      {Array.from({ length: filas }).map((_, i) => (
        <div
          key={i}
          className="rounded-xl bg-surface-container-lowest border border-outline-variant/50
            border-l-4 border-l-surface-container-high p-md shadow-card space-y-sm"
        >
          <div className="flex items-center gap-sm">
            <SkeletonLinea className="h-5 w-48" />
            <SkeletonLinea className="h-5 w-20" />
          </div>
          <SkeletonLinea className="h-4 w-28" />
          <div className="flex items-center gap-md pt-base">
            <SkeletonLinea className="h-4 w-24" />
            <SkeletonLinea className="h-4 w-28" />
            <SkeletonLinea className="h-4 w-20" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function ListaVacia() {
  return (
    <div className="flex flex-col items-center text-center py-xxl gap-sm">
      <div className="w-16 h-16 rounded-2xl bg-surface-container-high text-on-surface-variant
        flex items-center justify-center mb-base">
        <Icon name="video_library" className="text-[32px]" />
      </div>
      <p className="font-headline text-title-lg text-on-surface">Todavía no hay sesiones grabadas</p>
      <p className="text-body-md text-on-surface-variant max-w-sm">
        Iniciá el harness de diagnóstico y presioná <strong>Grabar sesión</strong> para registrar
        eventos y revisarlos acá.
      </p>
    </div>
  );
}
