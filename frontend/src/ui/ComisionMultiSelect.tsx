/**
 * ComisionMultiSelect — elegir una o varias comisiones, mostradas como chips.
 *
 * Hermano de ComisionSelect (que elige una sola). Se usa al crear un examen para
 * varias comisiones: cada comisión elegida se agrega como chip y se puede sacar
 * de a una.
 *
 * Regla que impone el componente: **todas las comisiones son de la misma
 * materia**. Al elegir la primera, la materia queda fijada y el desplegable
 * ofrece solo las comisiones de esa materia. El motivo es del dominio, no de la
 * UI: el examen se arma con el banco de preguntas de una materia, y una comisión
 * de otra materia recibiría preguntas que no cursa (el backend lo rechaza con
 * `comision_de_otra_materia`).
 */
import { useEffect, useMemo, useState } from 'react';
import { api } from '../lib/api';
import { ChipMultiSelect } from './ChipMultiSelect';
import type { ComisionConMateria } from '../lib/types';

export interface ComisionMultiSelectProps {
  value: string[];
  onChange: (comisionIds: string[], comisiones: ComisionConMateria[]) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  id?: string;
}

const DEFAULT_CLASS =
  'rounded-lg border border-surface-300 px-3 py-2 text-label-md text-on-surface focus:border-primary focus:outline-none disabled:bg-surface-100 disabled:text-on-surface-variant disabled:cursor-not-allowed';

export function ComisionMultiSelect({
  value,
  onChange,
  placeholder = 'Agregá una comisión',
  disabled = false,
  className = DEFAULT_CLASS,
  id,
}: ComisionMultiSelectProps) {
  const [comisiones, setComisiones] = useState<ComisionConMateria[]>([]);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    let cancelado = false;
    setCargando(true);
    api
      .comisionesTodas()
      .then((items) => {
        if (!cancelado) setComisiones(items);
      })
      .catch(() => {
        if (!cancelado) setComisiones([]);
      })
      .finally(() => {
        if (!cancelado) setCargando(false);
      });
    return () => {
      cancelado = true;
    };
  }, []);

  const porId = useMemo(
    () => new Map(comisiones.map((c) => [c.id, c])),
    [comisiones],
  );
  const elegidas = useMemo(
    () => value.map((v) => porId.get(v)).filter((c): c is ComisionConMateria => !!c),
    [value, porId],
  );

  // La materia la fija la primera comisión elegida. Mientras no haya ninguna,
  // están todas disponibles.
  const materiaFijada = elegidas[0]?.materia_id ?? null;
  const disponibles = comisiones.filter(
    (c) => !value.includes(c.id) && (materiaFijada === null || c.materia_id === materiaFijada),
  );

  const emitir = (ids: string[]) => {
    onChange(
      ids,
      ids.map((i) => porId.get(i)).filter((c): c is ComisionConMateria => !!c),
    );
  };

  const agregar = (comisionId: string) => {
    if (!comisionId || value.includes(comisionId)) return;
    emitir([...value, comisionId]);
  };

  const quitar = (comisionId: string) => emitir(value.filter((v) => v !== comisionId));

  const textoOpcionVacia = cargando
    ? 'Cargando comisiones…'
    : disponibles.length === 0
      ? elegidas.length > 0
        ? 'No quedan comisiones de esta materia'
        : 'No hay comisiones disponibles'
      : placeholder;

  return (
    <div className="flex flex-col gap-2">
      <ChipMultiSelect
        id={id}
        className={className}
        disabled={disabled || cargando || disponibles.length === 0}
        seleccionados={elegidas.map((c) => ({
          id: c.id,
          textoOpcion: `${c.codigo} - ${c.materia_nombre}`,
          textoChip: c.codigo,
        }))}
        disponibles={disponibles.map((c) => ({
          id: c.id,
          textoOpcion: `${c.codigo} - ${c.materia_nombre}`,
        }))}
        onAgregar={agregar}
        onQuitar={quitar}
        textoOpcionVacia={textoOpcionVacia}
      />

      {materiaFijada !== null && (
        <p className="text-label-sm text-on-surface-variant">
          Materia: <span className="text-on-surface">{elegidas[0].materia_nombre}</span>.
          Solo se pueden sumar comisiones de esta materia, porque el examen se arma con
          su banco de preguntas.
        </p>
      )}
    </div>
  );
}

export default ComisionMultiSelect;
