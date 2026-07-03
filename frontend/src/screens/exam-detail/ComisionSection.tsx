import { useEffect, useState } from 'react';
import { Button, Card, Icon, SectionTitle } from '../../ui/components';
import { api } from '../../lib/api';
import { asociarExamenAComision } from '../../lib/examContentAdmin';
import type { Comision, Materia } from '../../lib/types';

const SOFT_INPUT_CLS =
  'w-full rounded-md border border-outline-variant bg-surface px-3 py-2.5 text-sm ' +
  'text-on-surface outline-none transition-colors hover:border-outline focus:border-primary ' +
  'disabled:opacity-50 disabled:cursor-not-allowed';
const SOFT_LABEL_CLS = 'block text-sm font-medium text-on-surface';

interface Props {
  examenId: string;
  materiaActual: string | null | undefined;
  comisionActual: string | null | undefined;
  onAsociada: () => void;
}

export function ComisionSection({ examenId, materiaActual, comisionActual, onAsociada }: Props) {
  const [editando, setEditando] = useState(false);

  const [materias, setMaterias] = useState<Materia[]>([]);
  const [materiaId, setMateriaId] = useState('');
  const [comisiones, setComisiones] = useState<Comision[]>([]);
  const [comisionId, setComisionId] = useState('');
  const [cargandoMaterias, setCargandoMaterias] = useState(false);
  const [cargandoComisiones, setCargandoComisiones] = useState(false);

  const [guardando, setGuardando] = useState(false);
  const [ok, setOk] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!editando) return;
    let cancelado = false;
    setCargandoMaterias(true);
    api
      .materiasDisponibles()
      .then((items) => {
        if (!cancelado) setMaterias(items);
      })
      .catch(() => {
        if (!cancelado) setMaterias([]);
      })
      .finally(() => {
        if (!cancelado) setCargandoMaterias(false);
      });
    return () => {
      cancelado = true;
    };
  }, [editando]);

  useEffect(() => {
    if (!materiaId) {
      setComisiones([]);
      setComisionId('');
      return;
    }
    let cancelado = false;
    setCargandoComisiones(true);
    setComisionId('');
    api
      .comisionesDeMateria(materiaId)
      .then((items) => {
        if (!cancelado) setComisiones(items);
      })
      .catch(() => {
        if (!cancelado) setComisiones([]);
      })
      .finally(() => {
        if (!cancelado) setCargandoComisiones(false);
      });
    return () => {
      cancelado = true;
    };
  }, [materiaId]);

  function abrir() {
    setEditando(true);
    setOk(false);
    setError(null);
    setMateriaId('');
    setComisionId('');
  }

  function cancelar() {
    setEditando(false);
    setError(null);
  }

  async function guardar() {
    if (!comisionId) return;
    setGuardando(true);
    setError(null);
    setOk(false);
    try {
      await asociarExamenAComision(examenId, comisionId);
      setOk(true);
      setEditando(false);
      onAsociada();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'No se pudo asociar la comisión.');
    } finally {
      setGuardando(false);
    }
  }

  const actual = [materiaActual, comisionActual].filter(Boolean).join(' · ');

  return (
    <Card>
      <SectionTitle
        sub="Materia y comisión a la que pertenece este examen importado."
        action={
          !editando ? (
            <Button variant="outline" size="sm" icon="edit" onClick={abrir}>
              Cambiar comisión
            </Button>
          ) : undefined
        }
      >
        Comisión asociada
      </SectionTitle>

      <div className="space-y-4">
        {ok && (
          <div
            role="status"
            className="flex items-center gap-sm text-success bg-success-container rounded-md px-3 py-2.5 text-label-sm"
          >
            <Icon name="check_circle" className="text-[18px] shrink-0" fill />
            Comisión asociada.
          </div>
        )}
        {error && (
          <div
            role="alert"
            className="flex items-center gap-sm text-error bg-error-container/40 rounded-md px-3 py-2.5 text-label-sm"
          >
            <Icon name="error" className="text-[18px] shrink-0" fill />
            {error}
          </div>
        )}

        {!editando ? (
          <div className="flex items-center gap-sm">
            <Icon name="group" className="text-[20px] text-on-surface-variant shrink-0" />
            <p className="text-label-md text-on-surface">
              {actual || <span className="text-outline italic">— sin materia / comisión asignada</span>}
            </p>
          </div>
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className={SOFT_LABEL_CLS} htmlFor="comision-materia">
                  Materia
                </label>
                <select
                  id="comision-materia"
                  value={materiaId}
                  onChange={(e) => setMateriaId(e.target.value)}
                  disabled={cargandoMaterias || guardando}
                  className={`${SOFT_INPUT_CLS} mt-2`}
                >
                  <option value="">
                    {cargandoMaterias ? 'Cargando materias…' : 'Elegí una materia'}
                  </option>
                  {materias.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.nombre}
                      {m.codigo ? ` (${m.codigo})` : ''}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className={SOFT_LABEL_CLS} htmlFor="comision-comision">
                  Comisión
                </label>
                <select
                  id="comision-comision"
                  value={comisionId}
                  onChange={(e) => setComisionId(e.target.value)}
                  disabled={!materiaId || cargandoComisiones || guardando}
                  className={`${SOFT_INPUT_CLS} mt-2`}
                >
                  <option value="">
                    {!materiaId
                      ? 'Elegí primero una materia'
                      : cargandoComisiones
                        ? 'Cargando comisiones…'
                        : 'Elegí una comisión'}
                  </option>
                  {comisiones.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.nombre}
                      {c.codigo ? ` (${c.codigo})` : ''}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <p className="text-xs text-on-surface-variant">
              ¿No encontrás la materia o comisión? Creala en{' '}
              <span className="font-medium text-on-surface">Administración → Materias</span>.
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={cancelar} disabled={guardando}>
                Cancelar
              </Button>
              <Button
                variant="primary"
                size="sm"
                icon={guardando ? undefined : 'save'}
                onClick={guardar}
                disabled={guardando || !comisionId}
              >
                {guardando ? 'Guardando…' : 'Guardar comisión'}
              </Button>
            </div>
          </>
        )}
      </div>
    </Card>
  );
}
