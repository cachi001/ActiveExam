/**
 * ComisionSelect — selector combinado único de comisión.
 *
 * Reemplaza el patrón de dos selects encadenados (Materia → Comisión) por
 * uno solo, con las opciones ya formateadas "CÓDIGO - Materia" (igual al
 * ecosistema de referencia: no hace falta elegir materia primero para llegar
 * a la comisión, y la materia queda visible en cada opción).
 */
import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import type { ComisionConMateria } from '../lib/types';

export interface ComisionSelectProps {
  value: string;
  onChange: (comisionId: string, comision: ComisionConMateria | null) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  id?: string;
}

const DEFAULT_CLASS =
  'rounded-lg border border-surface-300 px-3 py-2 text-label-md text-on-surface focus:border-primary focus:outline-none disabled:bg-surface-100 disabled:text-on-surface-variant disabled:cursor-not-allowed';

export function ComisionSelect({
  value,
  onChange,
  placeholder = 'Elegí una comisión',
  disabled = false,
  className = DEFAULT_CLASS,
  id,
}: ComisionSelectProps) {
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

  return (
    <select
      id={id}
      value={value}
      disabled={disabled || cargando}
      onChange={(e) => {
        const id = e.target.value;
        const comision = comisiones.find((c) => c.id === id) ?? null;
        onChange(id, comision);
      }}
      className={className}
    >
      <option value="">{cargando ? 'Cargando comisiones…' : placeholder}</option>
      {comisiones.map((c) => (
        <option key={c.id} value={c.id}>
          {c.codigo} - {c.materia_nombre}
        </option>
      ))}
    </select>
  );
}

export default ComisionSelect;
