/**
 * SorteoSection — cómo resuelve sus preguntas un examen sorteado (c-78 E-07/E-08).
 *
 * Solo aparece si el examen sortea por intento. Muestra, por tramo, cuántas
 * preguntas hay copiadas en el examen contra cuántas se sortean (15.4), y avisa si
 * el banco creció desde que se armó.
 *
 * El pool está congelado a propósito: es lo que garantiza que mover, reclasificar
 * o borrar preguntas del banco no pueda dejar a un alumno sin examen. Incorporar
 * las nuevas es una decisión explícita del docente, y se bloquea una vez que
 * alguien rindió — si no, dos alumnos sortearían de conjuntos distintos.
 */
import { useCallback, useEffect, useState } from 'react';
import { Button, Card, Icon, LoadingSpinner, SectionTitle } from '../../ui/components';
import { useToast } from '../../ui/toast';
import { API_BASE } from '../../lib/api';
import { authProvider } from '../../lib/authProvider';
import {
  actualizarPoolDelExamenFn,
  leerSorteoDelExamenFn,
  type SorteoDelExamen,
} from '../../lib/examContentCatalog';

interface Props {
  examenId: string;
}

/** Preguntas que comparten dos alumnos, en promedio: largo² / pool. */
function repeticionEstimada(largo: number, pool: number): number | null {
  if (largo <= 0 || pool <= 0) return null;
  return Math.round((largo * largo) / pool);
}

export function SorteoSection({ examenId }: Props) {
  const toast = useToast();
  const [sorteo, setSorteo] = useState<SorteoDelExamen | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actualizando, setActualizando] = useState(false);

  const cargar = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      setSorteo(await leerSorteoDelExamenFn(API_BASE, authProvider.getToken(), examenId));
    } catch (err: unknown) {
      // D16: un fallo de carga NO se renderiza como "no hay sorteo".
      setError(err instanceof Error ? err.message : 'No se pudo cargar el sorteo.');
    } finally {
      setCargando(false);
    }
  }, [examenId]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  const actualizarPool = async () => {
    setActualizando(true);
    try {
      const nuevo = await actualizarPoolDelExamenFn(
        API_BASE,
        authProvider.getToken(),
        examenId,
      );
      setSorteo(nuevo);
      toast.success('Las preguntas nuevas del banco ya entran al sorteo.');
    } catch (err: unknown) {
      toast.error(
        err instanceof Error ? err.message : 'No se pudo actualizar el pool.',
      );
    } finally {
      setActualizando(false);
    }
  };

  if (cargando) {
    return (
      <Card>
        <LoadingSpinner size="sm" label="Cargando el sorteo…" />
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <div
          role="alert"
          className="flex items-center gap-sm text-error bg-error-container/40 rounded-md px-3 py-2.5 text-label-sm"
        >
          <Icon name="error" className="text-[18px] shrink-0" fill />
          {error}
        </div>
      </Card>
    );
  }

  // Un examen con preguntas fijas no tiene nada que mostrar acá.
  if (!sorteo || sorteo.modo_preguntas !== 'sorteo_por_intento') return null;

  const repite = repeticionEstimada(sorteo.largo_del_examen, sorteo.pool_total);
  const proporcion =
    repite !== null && sorteo.largo_del_examen > 0 ? repite / sorteo.largo_del_examen : 0;

  return (
    <Card>
      <SectionTitle
        icon="shuffle"
        sub="Cada alumno recibe preguntas distintas, sorteadas cuando entra a rendir."
      >
        Sorteo de preguntas
      </SectionTitle>

      <div className="space-y-4">
        <div className="rounded-xl bg-surface-100 px-4 py-3">
          <p className="text-label-md text-on-surface">
            Cada alumno rinde{' '}
            <strong>
              {sorteo.largo_del_examen}{' '}
              {sorteo.largo_del_examen === 1 ? 'pregunta' : 'preguntas'}
            </strong>
            , sorteadas de un conjunto de <strong>{sorteo.pool_total}</strong>.
          </p>
          {repite !== null && (
            <p className="text-label-sm text-on-surface-variant mt-1">
              Dos alumnos comparten alrededor de {repite} de {sorteo.largo_del_examen}.{' '}
              {proporcion >= 0.6
                ? 'Es mucho: para que se note, cargá más preguntas al banco o acortá el examen.'
                : proporcion >= 0.3
                  ? 'Se puede mejorar cargando más preguntas al banco.'
                  : 'Buena variedad.'}
            </p>
          )}
        </div>

        {/* 15.4: el desglose por tramo */}
        <div className="rounded-xl border border-outline-variant/40 overflow-hidden">
          {sorteo.tramos.map((t, i) => (
            <div
              key={`${t.categoria_id ?? 'sin'}-${i}`}
              className="flex items-center gap-3 px-4 py-2.5 border-b border-outline-variant/20 last:border-b-0"
            >
              <Icon
                name={t.categoria_id ? 'folder' : 'folder_off'}
                className="text-[16px] shrink-0 text-on-surface-variant"
              />
              <div className="flex-1 min-w-0">
                <div className="text-label-md text-on-surface truncate">
                  {t.categoria_nombre ?? 'Sin clasificar'}
                  {t.incluir_subcategorias && t.categoria_id && (
                    <span className="text-on-surface-variant"> y sus subcategorías</span>
                  )}
                </div>
                {t.tipos && t.tipos.length > 0 && (
                  <div className="text-label-sm text-on-surface-variant">
                    Solo {t.tipos.join(', ')}
                  </div>
                )}
              </div>
              <span className="shrink-0 text-label-sm text-on-surface-variant">
                sortea <strong className="text-on-surface">{t.cantidad}</strong> de{' '}
                <strong className="text-on-surface">{t.en_el_pool}</strong>
                {t.en_el_banco > t.en_el_pool && (
                  <span className="text-warning">
                    {' '}
                    ({t.en_el_banco - t.en_el_pool} nuevas en el banco)
                  </span>
                )}
              </span>
            </div>
          ))}
        </div>

        {sorteo.nuevas_en_el_banco > 0 && (
          <div className="rounded-xl border border-warning/40 bg-warning-container/30 px-4 py-3">
            <p className="text-label-md text-on-surface">
              El banco tiene{' '}
              <strong>
                {sorteo.nuevas_en_el_banco}{' '}
                {sorteo.nuevas_en_el_banco === 1 ? 'pregunta nueva' : 'preguntas nuevas'}
              </strong>{' '}
              que este examen todavía no usa.
            </p>
            <p className="text-label-sm text-on-surface-variant mt-1">
              El examen no las incorpora solo: trabaja con una copia congelada, y eso es
              lo que hace que tocar el banco no pueda romperlo mientras se rinde.
            </p>
            {sorteo.pool_editable ? (
              <div className="flex justify-end mt-2">
                <Button
                  variant="outline"
                  size="sm"
                  icon={actualizando ? undefined : 'library_add'}
                  onClick={actualizarPool}
                  disabled={actualizando}
                >
                  {actualizando ? 'Incorporando…' : 'Incorporarlas al examen'}
                </Button>
              </div>
            ) : (
              <p className="text-label-sm text-on-surface-variant mt-2">
                No se pueden incorporar: el examen ya tiene {sorteo.total_intentos}{' '}
                {sorteo.total_intentos === 1 ? 'intento rendido' : 'intentos rendidos'}, y
                cambiarlo ahora haría que dos alumnos rindan exámenes distintos.
              </p>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}
