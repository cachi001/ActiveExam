/**
 * ComisionesDelExamenSection — qué comisiones rinden este examen (c-78 E-06, 14.4).
 *
 * Bajo el modelo replicado (D12), un examen sirve a UNA comisión y las demás
 * comisiones tienen su propia copia con las mismas preguntas. Esta sección
 * presenta ese conjunto como lo que es para quien lo usa: la lista de comisiones
 * que rinden el examen, con un botón para sumar otra y otro para sacarla.
 *
 * Regla del dueño: una comisión con intentos rendidos NO se puede quitar. El
 * botón queda deshabilitado y dice por qué, en vez de dejar intentarlo y fallar.
 */
import { useCallback, useEffect, useState } from 'react';
import { Button, Card, Icon, LoadingSpinner, SectionTitle } from '../../ui/components';
import { ConfirmModal } from '../../ui/ConfirmModal';
import { useToast } from '../../ui/toast';
import { API_BASE, api } from '../../lib/api';
import { authProvider } from '../../lib/authProvider';
import {
  agregarComisionAlExamenFn,
  listarComisionesDelExamenFn,
  quitarComisionDelExamenFn,
  type ComisionDelExamen,
} from '../../lib/examContentCatalog';
import type { Comision } from '../../lib/types';

const SELECT_CLS =
  'w-full rounded-lg border border-surface-300 bg-white px-3 py-2.5 text-sm shadow-sm ' +
  'text-on-surface transition-colors hover:border-surface-400 focus:border-surface-500 focus:outline-none ' +
  'disabled:bg-surface-100 disabled:text-on-surface-variant disabled:border-surface-200 disabled:cursor-not-allowed';

interface Props {
  examenId: string;
  materiaId: string | null | undefined;
  /** Se llama tras agregar o quitar, para que la pantalla refresque el encabezado. */
  onCambio: () => void;
}

export function ComisionesDelExamenSection({ examenId, materiaId, onCambio }: Props) {
  const toast = useToast();
  const [items, setItems] = useState<ComisionDelExamen[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [candidatas, setCandidatas] = useState<Comision[]>([]);
  const [aAgregar, setAAgregar] = useState('');
  const [guardando, setGuardando] = useState(false);
  const [aQuitar, setAQuitar] = useState<ComisionDelExamen | null>(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      setItems(await listarComisionesDelExamenFn(API_BASE, authProvider.getToken(), examenId));
    } catch (err: unknown) {
      // D16: un fallo de carga NO se renderiza como "no hay comisiones".
      setError(err instanceof Error ? err.message : 'No se pudieron cargar las comisiones.');
    } finally {
      setCargando(false);
    }
  }, [examenId]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  // Las candidatas salen de la materia del examen: una comisión de otra materia
  // recibiría preguntas de un banco que no cursa (el backend lo rechaza igual).
  useEffect(() => {
    if (!materiaId) {
      setCandidatas([]);
      return;
    }
    let cancelado = false;
    api
      .comisionesDeMateria(materiaId)
      .then((cs) => {
        if (!cancelado) setCandidatas(cs);
      })
      .catch(() => {
        if (!cancelado) setCandidatas([]);
      });
    return () => {
      cancelado = true;
    };
  }, [materiaId]);

  const yaIncluidas = new Set(items.filter((i) => !i.dado_de_baja).map((i) => i.comision_id));
  const disponibles = candidatas.filter((c) => !yaIncluidas.has(c.id));

  const agregar = async () => {
    if (!aAgregar) return;
    setGuardando(true);
    try {
      const nueva = await agregarComisionAlExamenFn(
        API_BASE,
        authProvider.getToken(),
        examenId,
        aAgregar,
      );
      toast.success(`Se creó «${nueva.titulo}» con las mismas preguntas.`);
      setAAgregar('');
      await cargar();
      onCambio();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'No se pudo agregar la comisión.');
    } finally {
      setGuardando(false);
    }
  };

  const confirmarQuitar = async () => {
    const item = aQuitar;
    if (!item) return;
    setAQuitar(null);
    try {
      await quitarComisionDelExamenFn(
        API_BASE,
        authProvider.getToken(),
        examenId,
        item.comision_id,
      );
      toast.success(`${item.comision_codigo} ya no rinde este examen.`);
      await cargar();
      onCambio();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'No se pudo quitar la comisión.');
    }
  };

  const activas = items.filter((i) => !i.dado_de_baja);

  return (
    <Card>
      <SectionTitle
        icon="groups"
        sub="Cada comisión rinde su propia copia del examen, con las mismas preguntas."
      >
        Comisiones que rinden este examen
      </SectionTitle>

      <div className="space-y-4">
        {cargando && <LoadingSpinner size="sm" label="Cargando comisiones…" />}

        {error && (
          <div
            role="alert"
            className="flex items-center gap-sm text-error bg-error-container/40 rounded-md px-3 py-2.5 text-label-sm"
          >
            <Icon name="error" className="text-[18px] shrink-0" fill />
            {error}
          </div>
        )}

        {!cargando && !error && (
          <>
            <ul className="rounded-xl border border-outline-variant/40 overflow-hidden">
              {activas.map((item) => (
                <li
                  key={item.examen_id}
                  className="flex items-center gap-3 px-4 py-2.5 border-b border-outline-variant/20 last:border-b-0"
                >
                  <Icon
                    name="group"
                    className="text-[18px] shrink-0 text-on-surface-variant"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="text-label-md text-on-surface truncate">
                      {item.comision_codigo} · {item.comision_nombre}
                      {item.es_el_actual && (
                        <span className="ml-2 text-label-sm text-on-surface-variant">
                          (el que estás viendo)
                        </span>
                      )}
                    </div>
                    <div className="text-label-sm text-on-surface-variant truncate">
                      {item.titulo}
                      {item.total_intentos > 0 &&
                        ` · ${item.total_intentos} ${item.total_intentos === 1 ? 'intento rendido' : 'intentos rendidos'}`}
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    icon="close"
                    disabled={item.total_intentos > 0 || activas.length === 1}
                    title={
                      item.total_intentos > 0
                        ? 'No se puede quitar: esta comisión ya rindió el examen.'
                        : activas.length === 1
                          ? 'Es la única comisión del examen.'
                          : undefined
                    }
                    onClick={() => setAQuitar(item)}
                  >
                    Quitar
                  </Button>
                </li>
              ))}
            </ul>

            <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
              <label className="flex-1">
                <span className="block text-sm font-medium text-on-surface">
                  Sumar otra comisión
                </span>
                <select
                  value={aAgregar}
                  onChange={(e) => setAAgregar(e.target.value)}
                  disabled={guardando || disponibles.length === 0}
                  className={`${SELECT_CLS} mt-2`}
                >
                  <option value="">
                    {disponibles.length === 0
                      ? 'No quedan comisiones de esta materia'
                      : 'Elegí una comisión'}
                  </option>
                  {disponibles.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.nombre}
                      {c.codigo ? ` (${c.codigo})` : ''}
                    </option>
                  ))}
                </select>
              </label>
              <Button
                variant="primary"
                size="sm"
                icon={guardando ? undefined : 'add'}
                onClick={agregar}
                disabled={guardando || !aAgregar}
              >
                {guardando ? 'Agregando…' : 'Agregar'}
              </Button>
            </div>

            <p className="text-xs text-on-surface-variant">
              La comisión que sumes recibe una copia con las mismas preguntas, pero es un
              examen aparte: se configura y se corrige por separado.
            </p>
          </>
        )}
      </div>

      <ConfirmModal
        abierto={aQuitar !== null}
        titulo="Quitar la comisión"
        variante="danger"
        textoConfirmar="Quitar"
        mensaje={
          <p>
            {aQuitar?.comision_codigo} deja de rendir este examen. «{aQuitar?.titulo}» sale
            del catálogo y queda dado de baja, así que si te equivocás lo recuperás desde el
            filtro "Dados de baja" de la pantalla de Exámenes.
          </p>
        }
        onConfirmar={confirmarQuitar}
        onCancelar={() => setAQuitar(null)}
      />
    </Card>
  );
}
