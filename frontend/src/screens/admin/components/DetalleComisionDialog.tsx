/**
 * DetalleComisionDialog — la ficha completa de una comisión.
 *
 * Nace de un problema de la tabla: cada dato que se quiso mostrar como columna
 * la fue ensanchando, y la lista de tutores concatenados terminaba forzando
 * scroll horizontal que escondía columnas. La fila ahora muestra lo que
 * identifica a la comisión y CUÁNTOS tutores tiene; el resto vive acá, donde el
 * ancho no compite con nada.
 *
 * Es solo lectura: para cambiar tutores está "Gestionar tutores", para cambiar
 * los datos, "Editar comisión".
 */
import { Button, Icon } from '../../../ui/components';
import { ModalOverlay } from '../../../ui/ModalOverlay';
import type { Comision } from '../../../lib/types';

function Dato({ etiqueta, children }: { etiqueta: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] uppercase tracking-wider text-on-surface-variant">{etiqueta}</dt>
      <dd className="text-[13px] text-on-surface mt-0.5 break-words">{children}</dd>
    </div>
  );
}

const SIN_DATO = <span className="text-on-surface-variant">Sin definir</span>;

export function DetalleComisionDialog({
  comision,
  tutores,
  onCerrar,
}: {
  comision: Comision;
  /** Los tutores vigentes. Se pasan por separado porque el listado los mantiene
   *  en estado local mientras se los edita, y la comisión que viene del servidor
   *  todavía tendría los de antes. */
  tutores: { id: string; nombre: string }[];
  onCerrar: () => void;
}) {
  const activa = comision.activa !== false;
  return (
    <ModalOverlay etiqueta={`Detalle de ${comision.nombre}`} onCerrar={onCerrar}>
      <div className="card w-full max-w-lg p-lg max-h-[85vh] overflow-y-auto">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-title-sm font-semibold text-on-surface">{comision.nombre}</h2>
            <p className="text-label-sm text-on-surface-variant mt-0.5">
              {comision.codigo ?? 'Sin código'}
            </p>
          </div>
          {!activa && (
            <span className="shrink-0 inline-flex items-center gap-1 rounded-full bg-outline-variant/40 text-on-surface-variant px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide">
              <Icon name="pause_circle" className="text-[12px]" />
              Dada de baja
            </span>
          )}
        </div>

        <dl className="grid grid-cols-2 gap-4 mt-md">
          <Dato etiqueta="Período">{comision.periodo || SIN_DATO}</Dato>
          <Dato etiqueta="Año">{comision.anio ?? SIN_DATO}</Dato>
          <Dato etiqueta="Código de matriculación">
            {comision.codigo_matriculacion || SIN_DATO}
          </Dato>
          <Dato etiqueta="Inscriptos">{comision.total_inscriptos ?? 0}</Dato>
          <Dato etiqueta="Exámenes">{comision.total_examenes ?? 0}</Dato>
        </dl>

        <div className="mt-lg">
          <p className="text-[11px] uppercase tracking-wider text-on-surface-variant">
            Tutores a cargo ({tutores.length})
          </p>
          {tutores.length === 0 ? (
            // Sin tutor las notas quedan retenidas. Se dice acá y con el motivo,
            // no como un guion vacío que el docente tenga que interpretar.
            <p className="text-[13px] text-error mt-1.5 flex items-start gap-1.5">
              <Icon name="person_off" className="text-[16px] shrink-0 mt-0.5" />
              <span>
                Sin asignar. Las notas de esta comisión no se van a sincronizar con el
                campus hasta que tenga al menos un tutor.
              </span>
            </p>
          ) : (
            <ul className="mt-1.5 space-y-1">
              {tutores.map((t) => (
                <li key={t.id} className="text-[13px] text-on-surface flex items-center gap-2">
                  <Icon name="person" className="text-[16px] text-on-surface-variant shrink-0" />
                  <span className="break-words">{t.nombre}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="flex justify-end gap-sm mt-lg">
          <Button variant="primary" onClick={onCerrar}>
            Cerrar
          </Button>
        </div>
      </div>
    </ModalOverlay>
  );
}
