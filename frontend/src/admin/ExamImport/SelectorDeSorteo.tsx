/**
 * SelectorDeSorteo — de qué preguntas se arma un examen.
 *
 * Es LA pantalla de armado, y por eso vive aparte: la usan el modal de creación
 * y la edición del sorteo en el detalle del examen. Tenerla escrita dos veces
 * significaría que armar y editar el mismo examen se hacen distinto.
 *
 * Qué resuelve:
 *  - Sortear del banco (un número contra todo lo seleccionado) o repartir a mano
 *    por categoría.
 *  - El árbol de categorías con sus subcategorías, cada una con su tilde para
 *    dejarla afuera y su desglose para destildar preguntas puntuales (como
 *    Moodle, que deja ver la lista antes de sortear).
 *  - El filtro por tipo, que acota el examen y no solo la vista.
 *
 * No sabe de exámenes ni de endpoints: informa hacia arriba, por `onChange`, qué
 * sorteo quedó armado y si es válido. Quién lo guarda es cosa de quien lo usa.
 */
import { useEffect, useState } from 'react';
import { Icon, LoadingSpinner } from '../../ui/components';
import {
  listarCategorias,
  listarPreguntasBanco,
  type CategoriaPregunta,
  type PreguntaBanco,
} from '../../lib/apiAdmin/bancoPreguntasApi';
import { limpiarEnunciadoCloze } from '../../lib/cloze';
import { etiquetaDeTipo } from '../../lib/tiposPregunta';
import {
  construirTramos,
  estadoDeInclusion,
  estimarRepeticion,
  poolDelExamen,
  preguntasVisibles,
  type TramoSorteo,
} from './tramosDelBanco';

/** Rótulo de campo: mismo cuerpo que el valor, en gris. */
const LABEL_CLASS = 'text-label-md font-medium text-on-surface-variant';

/** Un tramo tal como lo espera el backend. */
export interface TramoDelPedido {
  categoria_id: string | null;
  cantidad: number;
  tipos: string[] | null;
  incluir_subcategorias: boolean;
}

/** Lo que el selector informa hacia arriba en cada cambio. */
export interface SorteoArmado {
  sorteo: TramoDelPedido[];
  /** Solo cuando se destildó alguna: si no, el pool es el banco entero. */
  pool_preguntas?: string[];
  /** Cuántas preguntas rinde cada alumno. */
  largo: number;
  /** Del total seleccionado. */
  poolTotal: number;
  valido: boolean;
}

interface Props {
  materiaId: string;
  onChange: (armado: SorteoArmado) => void;
  /** Precarga para editar un examen ya armado. */
  inicial?: { categoria_id: string | null; cantidad: number }[];
  /** Ids del banco que YA están en el pool del examen. Lo que no está acá se
   *  arranca destildado: es lo que el docente había sacado. */
  inicialPool?: string[];
}

/** "3 Cloze · 2 Opción múltiple", o "sin preguntas propias". */
function desgloseDeTipos(t: TramoSorteo): string {
  const partes = Object.entries(t.por_tipo).map(
    ([tipo, n]) => `${n} ${etiquetaDeTipo(tipo)}`,
  );
  return partes.length > 0 ? partes.join(' · ') : 'sin preguntas propias';
}

const SIN_CLASIFICAR = '__sin_clasificar__';

export function SelectorDeSorteo({ materiaId, onChange, inicial, inicialPool }: Props) {
  // Modo por defecto: UN número contra todo el banco. Repartir por categoría es
  // el caso avanzado (cubrir todas las unidades), no el habitual.
  const [porCategoria, setPorCategoria] = useState(false);
  const [cantidadTotal, setCantidadTotal] = useState('');
  // El árbol se DERIVA de estas dos listas y del tipo elegido, no se guarda: al
  // filtrar por tipo, una categoría que se queda sin preguntas tiene que
  // desaparecer, y un árbol guardado seguía mostrándola con conteos de otro tipo.
  const [categorias, setCategorias] = useState<CategoriaPregunta[]>([]);
  const [preguntas, setPreguntas] = useState<PreguntaBanco[]>([]);
  // Cuántas se piden de cada categoría, en el modo por categoría. Va por id y no
  // dentro del tramo justamente porque el tramo se recalcula.
  const [cantidades, setCantidades] = useState<Record<string, number>>({});
  const [excluidas, setExcluidas] = useState<Set<string>>(new Set());
  const [desplegada, setDesplegada] = useState<string | null>(null);
  const [tipoFiltro, setTipoFiltro] = useState<string | null>(null);
  const [cargandoCats, setCargandoCats] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setTipoFiltro(null);
    if (!materiaId) {
      setCategorias([]);
      setPreguntas([]);
      setExcluidas(new Set());
      setCantidades({});
      return;
    }
    // Todas las preguntas de la materia en UNA llamada, no una por categoría: el
    // endpoint sin `categoria_id` las devuelve todas con su categoría, y contar
    // por rama necesita verlas juntas igual.
    setCargandoCats(true);
    Promise.all([listarCategorias(materiaId), listarPreguntasBanco(materiaId)])
      .then(([cats, delBanco]) => {
        setCategorias(cats);
        setPreguntas(delBanco);
        setDesplegada(null);
        // Al editar, lo que no está en el pool del examen es lo que el docente
        // sacó: se arranca con eso destildado. Al crear, no hay nada excluido.
        setExcluidas(
          inicialPool
            ? new Set(
                delBanco.filter((p) => !inicialPool.includes(p.id)).map((p) => p.id),
              )
            : new Set(),
        );
        if (inicial && inicial.length > 0) {
          // Editar un examen ya armado: se precarga como lo dejó el docente. Un
          // tramo sin categoría es el modo simple (todo el banco).
          const porCat = inicial.some((t) => t.categoria_id !== null);
          setPorCategoria(porCat);
          if (porCat) {
            setCantidades(
              Object.fromEntries(
                inicial.map((t) => [t.categoria_id ?? SIN_CLASIFICAR, t.cantidad]),
              ),
            );
          } else {
            setCantidadTotal(String(inicial[0]?.cantidad ?? ''));
          }
        } else {
          setCantidades({});
        }
      })
      .catch(() => setError('No se pudieron cargar las categorías del banco.'))
      .finally(() => setCargandoCats(false));
  }, [materiaId]);

  const setCantidad = (t: TramoSorteo, val: number) => {
    const clave = t.categoria_id ?? SIN_CLASIFICAR;
    const tope = Math.max(0, Math.min(val, vivasDelTramo(t)));
    setCantidades((prev) => ({ ...prev, [clave]: tope }));
  };

  const alternarPregunta = (id: string) => {
    setExcluidas((prev) => {
      const siguiente = new Set(prev);
      if (siguiente.has(id)) siguiente.delete(id);
      else siguiente.add(id);
      return siguiente;
    });
  };

  // Destildar una categoría saca todas sus preguntas; volver a tildarla las
  // devuelve, incluso las que se habían sacado de a una.
  const alternarCategoria = (ids: string[], hayAlguna: boolean) => {
    setExcluidas((prev) => {
      const siguiente = new Set(prev);
      for (const id of ids) {
        if (hayAlguna) siguiente.add(id);
        else siguiente.delete(id);
      }
      return siguiente;
    });
  };

  // Tipos presentes en el banco de esta materia, para los chips de filtro.
  const tiposDisponibles = [...new Set(preguntas.map((p) => p.tipo))];

  // El chip de tipo acota lo que se ve Y lo que puede salir sorteado: filtrar
  // "Cloze" y que igual entrara una multichoice sería una sorpresa el día del
  // examen. Con "Todos" no filtra nada.
  const delTipoElegido = preguntasVisibles(preguntas, tipoFiltro);

  const claveDe = (t: TramoSorteo): string => t.categoria_id ?? SIN_CLASIFICAR;

  const tramos = construirTramos(categorias, delTipoElegido).map((t) => ({
    ...t,
    cantidad: cantidades[claveDe(t)] ?? 0,
  }));
  const tramosVisibles = tramos;

  // Las preguntas de una fila: las PROPIAS de esa categoría, del tipo que se
  // esté mirando. Es lo que se despliega y lo que se puede destildar de a una.
  const idsDelTramo = (t: TramoSorteo): string[] =>
    delTipoElegido
      .filter((p) => (p.categoria_id ?? null) === t.categoria_id)
      .map((p) => p.id);

  const vivasDelTramo = (t: TramoSorteo): number =>
    idsDelTramo(t).filter((id) => !excluidas.has(id)).length;

  // Lo que puede salir sorteado hoy: lo visible menos lo destildado.
  const pool = poolDelExamen(delTipoElegido, excluidas);
  const totalDelBanco = pool.length;

  const tramosActivos = tramos.filter((t) => t.cantidad > 0);
  const totalPreguntas = tramosActivos.reduce((s, t) => s + t.cantidad, 0);
  const poolDeLosTramos = tramosActivos.reduce((s, t) => s + vivasDelTramo(t), 0);

  // Repetición POR TRAMO y sumada, no un promedio global. El promedio diluía los
  // tramos flacos contra los grandes: con 4 de 30 más 1 de 1 más 1 de 1 decía
  // "Buena variedad" cuando 2 de las 6 preguntas son iguales para todo el curso.
  const repeticion = estimarRepeticion(
    tramosActivos.map((t) => ({ cantidad: t.cantidad, disponibles: vivasDelTramo(t) })),
  );
  const repeticionEstimada = totalPreguntas > 0 ? Math.round(repeticion.compartidas) : null;
  const proporcion = totalPreguntas > 0 ? repeticion.compartidas / totalPreguntas : 0;
  const consejoDeRepeticion =
    repeticion.fijas > 0
      ? `${repeticion.fijas} de las ${repeticion.total} las recibe todo el curso: esas categorías se agotan. Cargá más preguntas ahí, o pedí menos de esas categorías.`
      : proporcion >= 0.6
        ? 'Es mucho: para que se note, cargá más preguntas al banco o hacé el examen más corto.'
        : proporcion >= 0.3
          ? 'Se puede mejorar cargando más preguntas al banco o acortando el examen.'
          : 'Buena variedad.';

  const nTotal = Number(cantidadTotal) || 0;

  // Se informa hacia arriba en cada cambio: quien usa el selector no tiene que
  // rearmar el pedido ni volver a decidir si es válido.
  useEffect(() => {
    const valido = porCategoria
      ? tramosActivos.length > 0
      : nTotal > 0 && nTotal <= totalDelBanco;
    onChange({
      valido,
      largo: porCategoria ? totalPreguntas : nTotal,
      poolTotal: porCategoria ? poolDeLosTramos : totalDelBanco,
      // Solo cuando se sacó alguna: si no, el pool es el banco y no hace falta
      // viajar con cientos de ids.
      pool_preguntas: excluidas.size > 0 ? pool.map((p) => p.id) : undefined,
      // Sin categoría y con descendencia = TODO el banco. Es el modo por
      // defecto: un solo número contra todas las preguntas de la materia.
      sorteo: porCategoria
        ? tramosActivos.map((t) => ({
            categoria_id: t.categoria_id,
            cantidad: t.cantidad,
            tipos: tipoFiltro ? [tipoFiltro] : null,
            // Cada categoría aporta solo lo suyo: las hijas se eligen aparte en
            // la misma lista, así que incluirlas duplicaría preguntas.
            incluir_subcategorias: false,
          }))
        : [
            {
              categoria_id: null,
              cantidad: nTotal,
              tipos: tipoFiltro ? [tipoFiltro] : null,
              incluir_subcategorias: true,
            },
          ],
    });
    // `onChange` se deja afuera a propósito: si el padre lo recrea en cada
    // render, incluirlo dispara este efecto en loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [porCategoria, nTotal, totalPreguntas, totalDelBanco, tipoFiltro, excluidas, cantidades]);

  if (error) {
    return <p className="text-label-md text-error">{error}</p>;
  }

  return (
    <div>
        {/* El caso habitual: un número contra todo el banco. Repartir por
            categoría es lo avanzado (asegurar que entren las tres
            unidades), y antes era el único camino. */}
        <div className="rounded-lg border border-outline-variant/60 p-4 mb-3">
          {/* Antes el sorteo era el modo por defecto pero no se veía como
              una opción: había un solo tilde, el del reparto a mano, y el
              otro camino era "no tildar nada". Dos opciones explícitas
              dicen cuál está activa sin tener que deducirlo. */}
          <div className="flex flex-col gap-2 mb-3">
            <label className="flex items-start gap-2 cursor-pointer">
              <input
                type="radio"
                name="modo-de-armado"
                checked={!porCategoria}
                onChange={() => setPorCategoria(false)}
                className="accent-primary w-4 h-4 shrink-0 mt-0.5"
              />
              <span>
                <span className="text-label-md text-on-surface">
                  Sortear del banco
                </span>
                <span className="block text-label-sm font-normal text-on-surface-variant">
                  Un número contra todas las preguntas seleccionadas.
                </span>
              </span>
            </label>
            <label className="flex items-start gap-2 cursor-pointer">
              <input
                type="radio"
                name="modo-de-armado"
                checked={porCategoria}
                onChange={() => setPorCategoria(true)}
                className="accent-primary w-4 h-4 shrink-0 mt-0.5"
              />
              <span>
                <span className="text-label-md text-on-surface">
                  Elegir a mano cuántas de cada categoría
                </span>
                <span className="block text-label-sm font-normal text-on-surface-variant">
                  Para asegurar que entren todos los temas.
                </span>
              </span>
            </label>
          </div>
          {!porCategoria && (
          <>
          <label className={LABEL_CLASS}>
            ¿Cuántas preguntas va a tener el examen?
          </label>
          <div className="flex items-baseline gap-2 mt-1.5">
            <input
              type="number"
              min={1}
              max={totalDelBanco}
              value={cantidadTotal}
              placeholder="10"
              onChange={(e) => setCantidadTotal(e.target.value)}
              className="w-24 rounded-lg border border-surface-300 px-3 py-2 text-label-md font-normal text-on-surface text-right focus:border-primary focus:outline-none disabled:opacity-40"
            />
            <span className="text-label-md text-on-surface-variant">
              de las <strong className="text-on-surface">{totalDelBanco}</strong>{' '}
              {excluidas.size > 0
                ? 'que dejaste seleccionadas abajo'
                : 'que hay en el banco de esta materia'}
            </span>
          </div>
          {/* Pedir más de las que hay es el error fácil de cometer después
              de destildar media lista: el botón se apaga y acá se dice por
              qué, en vez de dejar que el backend responda 422. */}
          {nTotal > totalDelBanco && (
            <p className="text-label-sm text-error mt-2">
              No alcanzan: seleccionaste {totalDelBanco} y estás pidiendo{' '}
              {nTotal}.
            </p>
          )}
          {nTotal > 0 && nTotal <= totalDelBanco && (
            <p className="text-label-sm text-on-surface-variant mt-2">
              {nTotal === totalDelBanco
                ? 'Al pedir todas las que hay no queda nada para sortear: todos los alumnos van a rendir exactamente las mismas.'
                : `Cada alumno recibe ${nTotal} distintas, sorteadas de las ${totalDelBanco}. No se reparte por categoría: pueden salir todas de una o de varias.`}
            </p>
          )}
          </>
          )}
        </div>
        <p className={`${LABEL_CLASS} mb-2`}>
          {porCategoria
            ? 'Cuántas de cada categoría'
            : 'De dónde puede salir el sorteo'}
        </p>

        {cargandoCats && (
          <LoadingSpinner size="sm" label="Cargando categorías…" />
        )}

        {!cargandoCats && tramos.length === 0 && (
          <p className="text-label-md text-on-surface-variant italic text-center py-4">
            No hay preguntas en el banco para esta materia.
          </p>
        )}

        {!cargandoCats && tiposDisponibles.length > 1 && (
          <div className="flex flex-wrap items-center gap-1.5 mb-2">
            {/* No es un filtro de vista: elegir un tipo deja el examen con
                preguntas de ese tipo solamente. */}
            <span className="text-label-sm text-on-surface-variant mr-1">
              Tipo de pregunta:
            </span>
            <button
              type="button"
              onClick={() => setTipoFiltro(null)}
              className={`px-2.5 py-1 rounded-full text-label-sm border transition-colors ${
                tipoFiltro === null
                  ? 'bg-primary text-white border-primary'
                  : 'border-surface-300 text-on-surface-variant hover:border-primary'
              }`}
            >
              Todos ({preguntas.length})
            </button>
            {tiposDisponibles.map((tipo) => (
              <button
                key={tipo}
                type="button"
                onClick={() => setTipoFiltro(tipo)}
                className={`px-2.5 py-1 rounded-full text-label-sm border transition-colors ${
                  tipoFiltro === tipo
                    ? 'bg-primary text-white border-primary'
                    : 'border-surface-300 text-on-surface-variant hover:border-primary'
                }`}
              >
                {etiquetaDeTipo(tipo)} (
                {preguntas.filter((p) => p.tipo === tipo).length})
              </button>
            ))}
          </div>
        )}

        {!cargandoCats && tramos.length > 0 && (
          <div className="rounded-xl border border-outline-variant/40 overflow-hidden">
            {tramosVisibles.map((t, idx) => {
              const disponibles = vivasDelTramo(t);
              // Pedir todas las que hay no es sortear: esas preguntas las
              // recibe todo el curso.
              const esFija = t.cantidad > 0 && t.cantidad >= disponibles;
              // Una categoría puede no tener preguntas propias y existir
              // solo para colgar a sus hijas: ahí no hay nada que pedirle.
              const soloAgrupa = disponibles === 0 && t.disponibles_rama > 0;
              const ids = idsDelTramo(t);
              const clave = t.categoria_id ?? '__sin_clasificar__';
              const estado = estadoDeInclusion(ids, excluidas);
              const abierta = desplegada === clave;
              return (
              <div
                key={clave}
                className={
                  idx < tramos.length - 1 ? 'border-b border-outline-variant/20' : ''
                }
              >
              <div
                className={`flex items-center gap-3 px-4 py-2 ${
                  t.cantidad > 0 ? 'bg-primary/5' : ''
                }`}
                // Indentado según la profundidad: es lo que deja ver de qué
                // categoría cuelga cada subcategoría.
                style={{ paddingLeft: `${16 + t.profundidad * 20}px` }}
              >
                {/* El tilde saca la categoría entera del sorteo. Sin esto, la
                    única forma de dejar un tema afuera era borrar sus
                    preguntas del banco. */}
                <input
                  type="checkbox"
                  checked={estado === 'todas'}
                  ref={(el) => {
                    if (el) el.indeterminate = estado === 'algunas';
                  }}
                  disabled={ids.length === 0}
                  aria-label={`Incluir ${t.categoria_nombre}`}
                  onChange={() => alternarCategoria(ids, estado !== 'ninguna')}
                  className="accent-primary w-4 h-4 shrink-0 mt-1 self-start disabled:opacity-30"
                />
                <Icon
                  name={t.categoria_id ? 'folder' : 'folder_off'}
                  className={`text-[16px] shrink-0 mt-0.5 self-start ${
                    estado === 'ninguna'
                      ? 'text-on-surface-variant/40'
                      : 'text-on-surface-variant'
                  }`}
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline gap-2">
                    <span
                      className={`text-label-md truncate ${
                        estado === 'ninguna'
                          ? 'text-on-surface-variant/50 line-through'
                          : 'text-on-surface'
                      }`}
                      title={t.categoria_nombre}
                    >
                      {t.categoria_nombre}
                    </span>
                    {/* Al lado del nombre y no debajo del desglose: con tres
                        tipos mezclados el desglose ocupa dos renglones y el
                        enlace se movía de lugar según la categoría. */}
                    {ids.length > 0 && (
                      <button
                        type="button"
                        onClick={() => setDesplegada(abierta ? null : clave)}
                        className="text-label-sm text-primary hover:underline shrink-0"
                      >
                        {abierta ? 'ocultar' : 'ver las preguntas'}
                      </button>
                    )}
                  </div>
                  <div className="text-label-sm text-on-surface-variant flex items-center gap-2 flex-wrap">
                    {/* De qué está hecha la categoría. Antes el tipo partía
                        la fila en dos y la misma categoría aparecía
                        repetida, como si fueran dos temas distintos. */}
                    <span>{desgloseDeTipos(t)}</span>
                    {esFija && (
                      <span className="text-warning">· fija: la reciben todos</span>
                    )}
                  </div>
                </div>
                <span className="text-label-sm text-on-surface-variant shrink-0">
                  {soloAgrupa
                    ? `agrupa ${t.disponibles_rama}`
                    : `${disponibles} disp.`}
                </span>
                {porCategoria && !soloAgrupa && (
                  <input
                    type="number"
                    min={0}
                    max={disponibles}
                    value={t.cantidad || ''}
                    placeholder="0"
                    onChange={(e) =>
                      setCantidad(t, parseInt(e.target.value, 10) || 0)
                    }
                    className="w-16 rounded-lg border border-surface-300 px-2 py-1 text-label-md text-right text-on-surface focus:border-primary focus:outline-none"
                  />
                )}
              </div>
              {/* El desglose: en Moodle también se ven las preguntas de la
                  categoría antes de sortear. Es la única forma de sacar una
                  puntual sin darla de baja del banco. */}
              {abierta && (
                <div
                  className="bg-surface-50 py-1"
                  style={{ paddingLeft: `${36 + t.profundidad * 20}px` }}
                >
                  {ids.map((id) => {
                    const preg = preguntas.find((p) => p.id === id)!;
                    const dentro = !excluidas.has(id);
                    return (
                      <label
                        key={id}
                        className="flex items-start gap-2 px-3 py-1 cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={dentro}
                          onChange={() => alternarPregunta(id)}
                          className="accent-primary mt-0.5 shrink-0"
                        />
                        {/* Dos renglones: con una sola no entraba la
                            consigna y todas las cloze se leían igual. */}
                        <span
                          className={`text-label-sm line-clamp-2 ${
                            dentro
                              ? 'text-on-surface-variant'
                              : 'text-on-surface-variant/50 line-through'
                          }`}
                        >
                          <span className="text-on-surface-variant/70">
                            {etiquetaDeTipo(preg.tipo)}
                          </span>
                          {' · '}
                          {limpiarEnunciadoCloze(preg.enunciado) ||
                            '(sin enunciado)'}
                        </span>
                      </label>
                    );
                  })}
                </div>
              )}
              </div>
              );
            })}
          </div>
        )}

        {/* Cuánto se van a parecer dos exámenes: es la consecuencia directa de lo
            que se acaba de elegir, así que se dice acá. */}
        {repeticionEstimada !== null && (
          <p className="text-label-sm text-on-surface-variant mt-2">
            Dos alumnos van a compartir alrededor de {repeticionEstimada} de{' '}
            {totalPreguntas}. {consejoDeRepeticion}
          </p>
        )}

        {totalPreguntas > 0 && (
          <p className="text-label-sm text-on-surface-variant mt-2 text-right">
            Total:{' '}
            <span className="text-on-surface font-semibold">{totalPreguntas} preguntas</span>
            {/* Separar fijas de sorteadas es el punto: un total a secas
                esconde que parte del examen es igual para todo el curso. */}
            {repeticion.fijas > 0 && (
              <>
                {' · '}
                <span className="text-on-surface">{repeticion.sorteadas} sorteadas</span>
                {' y '}
                <span className="text-warning font-medium">{repeticion.fijas} fijas</span>
              </>
            )}
          </p>
        )}

      </div>
  );
}
