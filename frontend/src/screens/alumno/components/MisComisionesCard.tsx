/**
 * MisComisionesCard — muestra en el perfil del alumno EN QUÉ MATERIA Y COMISIÓN
 * está inscripto. Se apoya en los endpoints ya scopeados por inscripción:
 *   GET /exam-content/materias                 → solo materias inscriptas
 *   GET /exam-content/materias/{id}/comisiones → solo sus comisiones de esa materia
 * (el backend filtra por `InscripcionSqlRepository` para el rol alumno).
 *
 * Se hace su propio fetch al montar; degradación silenciosa si algo falla.
 */
import { useEffect, useState } from 'react';
import { Card, Icon, LoadingSpinner } from '../../../ui/components';
import { api } from '../../../lib/api';
import type { Comision } from '../../../lib/types';

interface MateriaComision {
  materiaNombre: string;
  materiaCodigo: string;
  comisiones: Comision[];
}

export function MisComisionesCard() {
  const [items, setItems] = useState<MateriaComision[] | null>(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    let vivo = true;
    (async () => {
      try {
        const materias = await api.materiasDisponibles();
        const conComisiones = await Promise.all(
          materias.map(async (m) => ({
            materiaNombre: m.nombre,
            materiaCodigo: m.codigo,
            comisiones: await api.comisionesDeMateria(m.id).catch(() => [] as Comision[]),
          })),
        );
        if (vivo) setItems(conComisiones.filter((x) => x.comisiones.length > 0));
      } catch {
        if (vivo) setItems([]);
      } finally {
        if (vivo) setCargando(false);
      }
    })();
    return () => { vivo = false; };
  }, []);

  return (
    <Card>
      <div className="flex items-center gap-3 mb-5">
        <Icon name="school" className="text-2xl text-on-surface-variant shrink-0" />
        <h2 className="text-xl font-semibold text-on-surface">Mi cursada</h2>
      </div>

      {cargando ? (
        <div className="py-4 flex justify-center">
          <LoadingSpinner size="sm" label="Cargando tu materia y comisión…" />
        </div>
      ) : !items || items.length === 0 ? (
        <p className="text-[14px] text-on-surface-variant">
          Todavía no estás inscripto en ninguna comisión.
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          {items.map((mat) =>
            mat.comisiones.map((c) => (
              <div
                key={c.id}
                className="flex items-start gap-3 rounded-xl border border-surface-200 bg-white px-4 py-3"
              >
                <div className="w-10 h-10 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0">
                  <Icon name="menu_book" className="text-[20px]" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-[15px] font-semibold text-on-surface leading-tight">
                    {mat.materiaNombre}
                  </p>
                  <p className="text-[13px] text-on-surface-variant mt-0.5">
                    {c.nombre}
                    {c.codigo ? ` · ${c.codigo}` : ''}
                    {[c.periodo, c.anio].filter(Boolean).length > 0
                      ? ` · ${[c.periodo, c.anio].filter(Boolean).join(' ')}`
                      : ''}
                  </p>
                  {c.tutores && c.tutores.length > 0 && (
                    <p className="text-[12px] text-on-surface-variant mt-1 flex items-center gap-1">
                      <Icon name="person" className="text-[14px]" />
                      {c.tutores.length === 1 ? 'Tutor: ' : 'Tutores: '}
                      {c.tutores.map((t) => t.nombre).join(', ')}
                    </p>
                  )}
                </div>
              </div>
            )),
          )}
        </div>
      )}
    </Card>
  );
}
