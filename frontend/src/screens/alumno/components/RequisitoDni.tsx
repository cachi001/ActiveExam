/**
 * RequisitoDni — sección de verificación documental (DNI) dentro del perfil.
 *
 * Extraída de StudentProfile (C-42) para mantener el contenedor ≤ 400 líneas.
 * Opcional y flaggeada (ENABLE_DNI_SCAN): nunca bloquea el perfil completo.
 */
import { Button } from '../../../ui/components';
import { RequisitoCard } from './RequisitoCard';
import type { EscaneDNI } from '../../../lib/types';

interface RequisitoDniProps {
  dni: EscaneDNI | null;
  dniOk: boolean;
  dniScanHabilitado: boolean;
  onEscanear: () => void;
}

export function RequisitoDni({ dni, dniOk, dniScanHabilitado, onEscanear }: RequisitoDniProps) {
  return (
    <RequisitoCard
      icon="badge"
      title="Verificación documental"
      badge={{
        tone: dniOk ? 'success' : 'neutral',
        label: dniOk ? 'Registrado' : dniScanHabilitado ? 'Pendiente' : 'No disponible',
      }}
    >
      {dniOk && dni ? (
        <div className="space-y-sm text-label-sm">
          <p className="text-on-surface-variant">
            Frente y dorso registrados el {new Date(dni.fecha_captura).toLocaleDateString('es-AR', {
              day: '2-digit', month: 'long', year: 'numeric',
            })}.
          </p>
          <p className="text-on-surface-variant">
            Se guarda cifrado y protegido, y se usa solo para verificar tu identidad.
          </p>
          {dniScanHabilitado && (
            <Button
              variant="ghost"
              size="sm"
              icon="refresh"
              onClick={onEscanear}
              className="text-label-sm text-on-surface-variant"
            >
              Rehacer escaneo
            </Button>
          )}
        </div>
      ) : dniScanHabilitado ? (
        <div className="space-y-md">
          <p className="text-label-sm text-on-surface-variant">
            El escaneo del DNI es opcional y no bloquea tu habilitación para rendir.
            Refuerza la verificación de identidad documental.
          </p>
          <Button variant="outline" size="sm" icon="badge" onClick={onEscanear} className="w-full sm:w-auto">
            Escanear DNI (opcional)
          </Button>
        </div>
      ) : (
        <p className="text-label-sm text-on-surface-variant">
          No disponible en esta versión. No bloquea el perfil completo. Cuando esté activo, tu DNI
          se va a guardar cifrado y protegido.
        </p>
      )}
    </RequisitoCard>
  );
}
