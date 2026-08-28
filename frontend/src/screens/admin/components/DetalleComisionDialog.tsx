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

/** Un dato de la ficha. La etiqueta arriba en chico, el valor abajo en grande:
 *  se lee primero el valor, que es lo que se vino a buscar. */
function Dato({ etiqueta, children }: { etiqueta: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-label-sm text-on-surface-variant">{etiqueta}</dt>
      <dd className="text-body-md text-on-surface mt-1 break-words">{children}</dd>
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
      <div className="w-full max-w-lg bg-white rounded-lg border border-surface-200 shadow-lg flex flex-col max-h-[85vh]">
        {/* Encabezado: el nombre manda, el código lo acompaña. Separado del cuerpo
            por un borde para que el scroll no lo pise. */}
        <header className="flex items-start justify-between gap-md px-lg pt-lg pb-md border-b border-surface-200">
          <div className="min-w-0">
            <h2 className="text-title-lg text-on-surface truncate">{comision.nombre}</h2>
            <p className="text-label-md text-on-surface-variant mt-0.5 font-mono">
              {comision.codigo ?? 'Sin código'}
            </p>
          </div>
          <div className="flex items-center gap-sm shrink-0">
            {!activa && (
              <span className="inline-flex items-center gap-1 rounded-full bg-surface-container text-on-surface-variant px-2.5 py-1 text-label-sm">
                <Icon name="pause_circle" className="text-[14px]" />
                Dada de baja
              </span>
            )}
            <button
              type="button"
              onClick={onCerrar}
              aria-label="Cerrar"
              className="w-8 h-8 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors"
            >
              <Icon name="close" className="text-[20px]" />
            </button>
          </div>
        </header>

        <div className="px-lg py-lg space-y-lg overflow-y-auto">
          {/* Datos de cursado. Tres columnas para que período, año y matriculación
              entren en un renglón y no quede una celda huérfana abajo. */}
          <section>
            <h3 className="text-label-sm text-on-surface-variant uppercase tracking-wider mb-sm">
              Cursado
            </h3>
            <dl className="grid grid-cols-3 gap-md">
              <Dato etiqueta="Período">{comision.periodo || SIN_DATO}</Dato>
              <Dato etiqueta="Año">{comision.anio ?? SIN_DATO}</Dato>
              <Dato etiqueta="Código de matriculación">
                <span className="font-mono">{comision.codigo_matriculacion || SIN_DATO}</span>
              </Dato>
            </dl>
          </section>

          {/* Los números que importan, con el mismo peso visual entre sí. */}
          <section className="grid grid-cols-2 gap-md">
            <div className="rounded-lg border border-surface-200 px-md py-sm">
              <p className="text-label-sm text-on-surface-variant">Inscriptos</p>
              <p className="text-title-lg text-on-surface tabular-nums mt-0.5">
                {comision.total_inscriptos ?? 0}
              </p>
            </div>
            <div className="rounded-lg border border-surface-200 px-md py-sm">
              <p className="text-label-sm text-on-surface-variant">Exámenes</p>
              <p className="text-title-lg text-on-surface tabular-nums mt-0.5">
                {comision.total_examenes ?? 0}
              </p>
            </div>
          </section>

          <section>
            <h3 className="text-label-sm text-on-surface-variant uppercase tracking-wider mb-sm">
              Tutores a cargo ({tutores.length})
            </h3>
            {tutores.length === 0 ? (
              // Sin tutor las notas quedan retenidas. Se dice acá y con el motivo,
              // no como un guion vacío que el docente tenga que interpretar.
              <div className="flex items-start gap-sm rounded-lg bg-error-container/30 px-md py-sm">
                <Icon name="person_off" className="text-[20px] shrink-0 text-error mt-0.5" />
                <p className="text-body-md text-on-surface">
                  Sin asignar. Las notas de esta comisión no se van a sincronizar con el
                  campus hasta que tenga al menos un tutor.
                </p>
              </div>
            ) : (
              <ul className="rounded-lg border border-surface-200 divide-y divide-surface-200">
                {tutores.map((t) => (
                  <li key={t.id} className="flex items-center gap-sm px-md py-sm">
                    {/* Inicial en un avatar: da un punto de anclaje a cada renglón
                        y hace la lista escaneable cuando hay varios. */}
                    <span className="w-8 h-8 rounded-full bg-primary text-on-primary flex items-center justify-center font-semibold text-[13px] shrink-0">
                      {t.nombre.trim().charAt(0).toUpperCase()}
                    </span>
                    <span className="text-body-md text-on-surface break-words">{t.nombre}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>

        <footer className="flex justify-end px-lg py-md border-t border-surface-200">
          <Button variant="primary" onClick={onCerrar}>
            Cerrar
          </Button>
        </footer>
      </div>
    </ModalOverlay>
  );
}
