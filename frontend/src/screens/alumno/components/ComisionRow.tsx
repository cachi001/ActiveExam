import { Card, Icon, LoadingSpinner } from '../../../ui/components';
import type { Comision, ExamenContenidoResumen } from '../../../lib/types';

interface ComisionRowProps {
  comision: Comision;
  activa: boolean;
  cargandoExamenes: boolean;
  examenes: ExamenContenidoResumen[];
  onSelect: () => void;
  /** Navega a "Mis exámenes", donde se rinde (la comisión es solo informativa). */
  onIrAExamenes: () => void;
}

/** Subtítulo de la comisión: usa docente/horario (demo) o codigo/periodo/año (real, C-69). */
function subtituloComision(comision: Comision): string {
  if (comision.docente || comision.horario) {
    return [comision.docente, comision.horario].filter(Boolean).join(' · ');
  }
  const periodo = [comision.periodo, comision.anio].filter(Boolean).join(' ');
  return [comision.codigo, periodo].filter(Boolean).join(' · ');
}

/** Fila de dato de la comisión (ícono + etiqueta + valor). */
function Dato({ icon, label, value }: { icon: string; label: string; value: string }) {
  return (
    <div className="flex items-center gap-2 text-[13px]">
      <Icon name={icon} className="text-[16px] text-on-surface-variant shrink-0" />
      <span className="text-on-surface-variant">{label}:</span>
      <span className="text-on-surface font-medium min-w-0 truncate">{value}</span>
    </div>
  );
}

/**
 * Fila de comisión en "Mis materias". Al abrirla muestra SOLO información de la
 * comisión (decisión del dueño): la rendición NO vive acá, se hace desde "Mis
 * exámenes". Por eso no hay botón "Rendir" — solo datos + un acceso a rendir.
 */
export function ComisionRow({
  comision,
  activa,
  cargandoExamenes,
  examenes,
  onSelect,
  onIrAExamenes,
}: ComisionRowProps) {
  const subtitulo = subtituloComision(comision);
  const periodo = [comision.periodo, comision.anio].filter(Boolean).join(' ');

  return (
    <div>
      <button
        onClick={onSelect}
        className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg border transition-colors text-left ${
          activa
            ? 'bg-white border-primary ring-1 ring-primary/15'
            : 'bg-white border-surface-200 hover:bg-surface-50 hover:border-primary/40'
        }`}
      >
        <Icon
          name="groups"
          className={`shrink-0 text-[20px] ${activa ? 'text-primary' : 'text-on-surface-variant'}`}
        />
        <div className="flex-1 min-w-0">
          <p className={`text-[14px] font-semibold leading-tight ${activa ? 'text-primary' : 'text-on-surface'}`}>
            {comision.nombre}
          </p>
          {subtitulo && (
            <p className="text-[12.5px] text-on-surface-variant leading-tight mt-0.5">
              {subtitulo}
            </p>
          )}
        </div>
        <Icon
          name={activa ? 'expand_less' : 'expand_more'}
          className={`text-[20px] shrink-0 ${activa ? 'text-primary' : 'text-on-surface-variant'}`}
        />
      </button>

      {activa && (
        <div className="mt-sm ml-lg">
          <Card className="p-md space-y-md">
            {/* Datos de la comisión (solo lectura) */}
            <div className="space-y-1.5">
              {comision.docente && <Dato icon="person" label="Docente" value={comision.docente} />}
              {comision.horario && <Dato icon="schedule" label="Horario" value={comision.horario} />}
              {periodo && <Dato icon="event" label="Período" value={periodo} />}
              {comision.codigo && <Dato icon="tag" label="Código" value={comision.codigo} />}
              {!comision.docente && !comision.horario && !periodo && !comision.codigo && (
                <p className="text-[13px] text-on-surface-variant">
                  Todavía no hay información adicional de esta comisión.
                </p>
              )}
            </div>

            {/* Exámenes: solo cantidad. Se rinden desde "Mis exámenes". */}
            <div className="pt-sm border-t border-surface-200">
              {cargandoExamenes ? (
                <LoadingSpinner size="sm" label="Cargando…" />
              ) : (
                <div className="flex items-center justify-between gap-md">
                  <p className="text-[13px] text-on-surface-variant inline-flex items-center gap-2">
                    <Icon name="assignment" className="text-[16px]" />
                    {examenes.length === 0
                      ? 'Sin exámenes disponibles'
                      : `${examenes.length} ${examenes.length === 1 ? 'examen disponible' : 'exámenes disponibles'}`}
                  </p>
                  {examenes.length > 0 && (
                    <button
                      onClick={onIrAExamenes}
                      className="text-[13px] text-primary hover:underline font-semibold shrink-0"
                    >
                      Ir a rendir →
                    </button>
                  )}
                </div>
              )}
            </div>

            <p className="text-[12px] text-on-surface-variant">
              Los exámenes se rinden desde <strong>Mis exámenes</strong>.
            </p>
          </Card>
        </div>
      )}
    </div>
  );
}
