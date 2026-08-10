import { useCallback, useEffect, useState } from 'react';
import { Badge, Button, Card, Icon, SectionTitle } from '../../ui/components';
import { getPreguntasExamen, setPreguntasSeleccion, sortearPreguntas, type PreguntaSeleccion } from '../../lib/examContentAdmin';
import { listarCategorias } from '../../lib/apiAdmin/bancoPreguntasApi';
import type { CategoriaPregunta } from '../../lib/apiAdmin/bancoPreguntasApi';
import { limpiarEnunciadoCloze } from '../../lib/cloze';

const TIPO_PREGUNTA_LABEL: Record<string, string> = {
  multichoice: 'Opción múltiple',
  truefalse: 'Verdadero / Falso',
  cloze: 'Cloze',
};

function tipoLabel(tipo: string): string {
  return TIPO_PREGUNTA_LABEL[tipo] ?? tipo;
}

/**
 * Aplana el listado de categorías a un orden DFS con su nivel de anidamiento,
 * para mostrar la jerarquía (padre → hijas) en el picker del sorteo.
 */
function aplanarConNivel(cats: CategoriaPregunta[]): Array<{ cat: CategoriaPregunta; nivel: number }> {
  const hijosDe = new Map<string | null, CategoriaPregunta[]>();
  for (const c of cats) {
    const key = c.categoria_padre_id ?? null;
    if (!hijosDe.has(key)) hijosDe.set(key, []);
    hijosDe.get(key)!.push(c);
  }
  const orden: Array<{ cat: CategoriaPregunta; nivel: number }> = [];
  const idsConocidos = new Set(cats.map((c) => c.id));
  const visitar = (padreId: string | null, nivel: number) => {
    for (const c of hijosDe.get(padreId) ?? []) {
      orden.push({ cat: c, nivel });
      visitar(c.id, nivel + 1);
    }
  };
  visitar(null, 0);
  // Categorías cuyo padre no está en la lista (huérfanas) se muestran como raíz.
  for (const c of cats) {
    if (c.categoria_padre_id && !idsConocidos.has(c.categoria_padre_id) && !orden.some((o) => o.cat.id === c.id)) {
      orden.push({ cat: c, nivel: 0 });
    }
  }
  return orden;
}

type ModoSeleccion = 'manual' | 'sorteo';

interface Props {
  examenId: string;
  materiaId?: string | null;
  onSeleccionGuardada: (cantidad: number) => void;
}

export function PreguntasSeleccionSection({ examenId, materiaId, onSeleccionGuardada }: Props) {
  const [preguntas, setPreguntas] = useState<PreguntaSeleccion[]>([]);
  const [seleccionOriginal, setSeleccionOriginal] = useState<Record<string, boolean>>({});
  const [total, setTotal] = useState(0);
  const [bloqueada, setBloqueada] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState<string | null>(null);

  const [guardando, setGuardando] = useState(false);
  const [okGuardado, setOkGuardado] = useState(false);
  const [errorGuardar, setErrorGuardar] = useState<string | null>(null);

  // Modo de selección
  const [modo, setModo] = useState<ModoSeleccion>('manual');

  // Sorteo
  const [categorias, setCategorias] = useState<CategoriaPregunta[]>([]);
  const [cargandoCats, setCargandoCats] = useState(false);
  const [catIdsSeleccionadas, setCatIdsSeleccionadas] = useState<Set<string>>(new Set());
  const [cantidadPorCategoria, setCantidadPorCategoria] = useState(5);
  const [ejecutandoSorteo, setEjecutandoSorteo] = useState(false);
  const [okSorteo, setOkSorteo] = useState<number | null>(null);
  const [errorSorteo, setErrorSorteo] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    setErrorCarga(null);
    try {
      const resp = await getPreguntasExamen(examenId);
      setPreguntas(resp.items);
      setSeleccionOriginal(Object.fromEntries(resp.items.map((p) => [p.id, p.seleccionada])));
      setTotal(resp.total);
      setBloqueada(resp.bloqueada ?? false);
    } catch (err: unknown) {
      setErrorCarga(err instanceof Error ? err.message : 'No se pudieron cargar las preguntas.');
      setPreguntas([]);
      setTotal(0);
      setBloqueada(false);
    } finally {
      setCargando(false);
    }
  }, [examenId]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  // Cargar categorías cuando se cambia al modo sorteo
  useEffect(() => {
    if (modo !== 'sorteo' || !materiaId) return;
    setCargandoCats(true);
    listarCategorias(materiaId)
      .then(setCategorias)
      .catch(() => setCategorias([]))
      .finally(() => setCargandoCats(false));
  }, [modo, materiaId]);

  const seleccionadas = preguntas.filter((p) => p.seleccionada).length;
  const ningunaMarcada = seleccionadas === 0;
  const hayCambiosSeleccion = preguntas.some((p) => p.seleccionada !== (seleccionOriginal[p.id] ?? false));

  function toggle(id: string) {
    setOkGuardado(false);
    setPreguntas((prev) =>
      prev.map((p) => (p.id === id ? { ...p, seleccionada: !p.seleccionada } : p)),
    );
  }

  function setTodas(valor: boolean) {
    setOkGuardado(false);
    setPreguntas((prev) => prev.map((p) => ({ ...p, seleccionada: valor })));
  }

  async function guardar() {
    if (ningunaMarcada || bloqueada) return;
    setGuardando(true);
    setOkGuardado(false);
    setErrorGuardar(null);
    const ids = preguntas.filter((p) => p.seleccionada).map((p) => p.id);
    try {
      const res = await setPreguntasSeleccion(examenId, ids);
      setSeleccionOriginal(Object.fromEntries(preguntas.map((p) => [p.id, p.seleccionada])));
      setOkGuardado(true);
      onSeleccionGuardada(res.seleccionadas);
    } catch (err: unknown) {
      setErrorGuardar(err instanceof Error ? err.message : 'No se pudo guardar la selección.');
    } finally {
      setGuardando(false);
    }
  }

  function toggleCategoria(id: string) {
    setCatIdsSeleccionadas((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
    setOkSorteo(null);
    setErrorSorteo(null);
  }

  async function ejecutarSorteo() {
    if (catIdsSeleccionadas.size === 0 || bloqueada) return;
    setEjecutandoSorteo(true);
    setOkSorteo(null);
    setErrorSorteo(null);
    try {
      const res = await sortearPreguntas(examenId, Array.from(catIdsSeleccionadas), cantidadPorCategoria);
      setOkSorteo(res.seleccionadas);
      onSeleccionGuardada(res.seleccionadas);
      // Recargar lista para reflejar la nueva selección
      await cargar();
    } catch (err: unknown) {
      setErrorSorteo(err instanceof Error ? err.message : 'No se pudo ejecutar el sorteo.');
    } finally {
      setEjecutandoSorteo(false);
    }
  }

  return (
    <Card>
      <SectionTitle
        icon="fact_check"
        sub={
          cargando
            ? 'Cargando preguntas…'
            : errorCarga
              ? undefined
              : `${seleccionadas} de ${total} pregunta${total !== 1 ? 's' : ''} seleccionada${seleccionadas !== 1 ? 's' : ''}`
        }
        action={
          !cargando && !errorCarga && preguntas.length > 0 && !bloqueada && modo === 'manual' ? (
            <div className="flex items-center gap-xs">
              <Button variant="ghost" size="sm" onClick={() => setTodas(true)} disabled={guardando}>
                Seleccionar todas
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setTodas(false)} disabled={guardando}>
                Quitar todas
              </Button>
            </div>
          ) : undefined
        }
      >
        Preguntas del examen
      </SectionTitle>

      {/* Selector de modo (solo cuando no está bloqueada y hay preguntas) */}
      {!bloqueada && !cargando && !errorCarga && preguntas.length > 0 && (
        <div className="inline-flex gap-xs mb-md p-xs bg-surface-100 rounded-lg border border-outline-variant">
          <button
            onClick={() => { setModo('manual'); setOkGuardado(false); }}
            className={`flex items-center gap-xs px-sm py-xs rounded-md text-label-sm font-medium transition-colors ${
              modo === 'manual'
                ? 'bg-white text-on-surface shadow-sm border border-outline-variant'
                : 'text-on-surface-variant hover:text-on-surface'
            }`}
          >
            <Icon name="checklist" className="text-[15px]" />
            Manual
          </button>
          {materiaId && (
            <button
              onClick={() => { setModo('sorteo'); setOkGuardado(false); }}
              className={`flex items-center gap-xs px-sm py-xs rounded-md text-label-sm font-medium transition-colors ${
                modo === 'sorteo'
                  ? 'bg-white text-on-surface shadow-sm border border-outline-variant'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              <Icon name="shuffle" className="text-[15px]" />
              Por sorteo
            </button>
          )}
        </div>
      )}

      {cargando && (
        <div className="space-y-2 animate-pulse">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-14 bg-surface-100 rounded-lg" />
          ))}
        </div>
      )}

      {!cargando && errorCarga && (
        <div className="space-y-md">
          <div className="flex items-center gap-sm text-error bg-error-container/40 rounded-xl px-md py-sm text-label-sm">
            <Icon name="error" className="text-[18px] shrink-0" fill />
            {errorCarga}
          </div>
          <Button variant="outline" size="sm" icon="refresh" onClick={cargar}>
            Reintentar
          </Button>
        </div>
      )}

      {!cargando && !errorCarga && preguntas.length === 0 && (
        <div className="text-center py-xl text-on-surface-variant space-y-base">
          <Icon name="quiz" className="text-[40px] text-outline" />
          <p className="text-label-md">Este examen no tiene preguntas en el pool importado.</p>
        </div>
      )}

      {/* Panel de sorteo */}
      {!cargando && !errorCarga && preguntas.length > 0 && modo === 'sorteo' && (
        <div className="space-y-md">
          {bloqueada && (
            <div className="flex items-start gap-sm text-warning bg-warning-container rounded-xl px-md py-sm text-label-sm">
              <Icon name="lock" className="text-[18px] shrink-0 mt-0.5" fill />
              <span>
                Selección <strong>congelada</strong>: este examen ya tiene intentos finalizados.
              </span>
            </div>
          )}

          {okSorteo !== null && (
            <div className="flex items-center gap-sm text-success bg-success-container rounded-xl px-md py-sm text-label-sm">
              <Icon name="check_circle" className="text-[18px] shrink-0" fill />
              Sorteo ejecutado: {okSorteo} pregunta{okSorteo !== 1 ? 's' : ''} seleccionada{okSorteo !== 1 ? 's' : ''}.
            </div>
          )}
          {errorSorteo && (
            <div className="flex items-center gap-sm text-error bg-error-container/40 rounded-xl px-md py-sm text-label-sm">
              <Icon name="error" className="text-[18px] shrink-0" fill />
              {errorSorteo}
            </div>
          )}

          {cargandoCats ? (
            <div className="space-y-2 animate-pulse">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-10 bg-surface-100 rounded-lg" />
              ))}
            </div>
          ) : categorias.length === 0 ? (
            <div className="flex items-center gap-sm text-on-surface-variant bg-surface-100 rounded-xl px-md py-sm text-label-sm">
              <Icon name="info" className="text-[18px] shrink-0" />
              Esta materia no tiene categorías definidas. Creá categorías en el Banco de preguntas primero.
            </div>
          ) : (
            <>
              <div>
                <p className="text-label-md font-medium text-on-surface mb-sm">
                  Categorías a incluir
                </p>
                <ul className="space-y-xs">
                  {aplanarConNivel(categorias).map(({ cat, nivel }) => (
                    <li key={cat.id}>
                      <label
                        style={{ marginLeft: nivel * 20 }}
                        className={`flex items-center gap-sm p-sm rounded-xl border cursor-pointer transition-colors select-none ${
                          catIdsSeleccionadas.has(cat.id)
                            ? 'border-primary/40 bg-primary-fixed/30'
                            : 'border-outline-variant/40 hover:bg-surface-container-low'
                        }`}
                      >
                        {nivel > 0 && (
                          <Icon name="subdirectory_arrow_right" className="text-[16px] text-on-surface-variant shrink-0" />
                        )}
                        <input
                          type="checkbox"
                          checked={catIdsSeleccionadas.has(cat.id)}
                          onChange={() => toggleCategoria(cat.id)}
                          disabled={bloqueada || ejecutandoSorteo}
                          className="w-4 h-4 accent-primary shrink-0 disabled:cursor-not-allowed"
                        />
                        <span className="text-label-md text-on-surface">{cat.nombre}</span>
                      </label>
                    </li>
                  ))}
                </ul>
                <p className="text-label-sm text-on-surface-variant mt-xs flex items-start gap-xs">
                  <Icon name="info" className="text-[15px] shrink-0 mt-0.5" />
                  El sorteo toma preguntas solo de las categorías marcadas. Las subcategorías
                  no se incluyen solas: marcá cada una que quieras sortear.
                </p>
              </div>

              <div className="flex items-center gap-sm">
                <label className="text-label-md text-on-surface font-medium whitespace-nowrap">
                  Cantidad por categoría
                </label>
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={cantidadPorCategoria}
                  onChange={(e) => {
                    const v = parseInt(e.target.value, 10);
                    if (!isNaN(v) && v >= 1) setCantidadPorCategoria(v);
                  }}
                  disabled={bloqueada || ejecutandoSorteo}
                  className="w-20 border border-outline-variant rounded-xl px-sm py-xs text-body-md text-center focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
                />
              </div>

              {!bloqueada && (
                <div className="flex justify-end">
                  <Button
                    variant="primary"
                    icon={ejecutandoSorteo ? undefined : 'shuffle'}
                    onClick={ejecutarSorteo}
                    disabled={ejecutandoSorteo || catIdsSeleccionadas.size === 0}
                  >
                    {ejecutandoSorteo ? 'Sorteando…' : 'Ejecutar sorteo'}
                  </Button>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Panel de selección manual */}
      {!cargando && !errorCarga && preguntas.length > 0 && modo === 'manual' && (
        <div className="space-y-md">
          {bloqueada && (
            <div className="flex items-start gap-sm text-warning bg-warning-container rounded-xl px-md py-sm text-label-sm">
              <Icon name="lock" className="text-[18px] shrink-0 mt-0.5" fill />
              <span>
                Selección <strong>congelada</strong>: este examen ya tiene intentos
                finalizados. Cambiar qué preguntas lo componen alteraría notas ya
                calculadas, por eso quedó bloqueada.
              </span>
            </div>
          )}
          {okGuardado && (
            <div className="flex items-center gap-sm text-success bg-success-container rounded-xl px-md py-sm text-label-sm">
              <Icon name="check_circle" className="text-[18px] shrink-0" fill />
              Selección guardada.
            </div>
          )}
          {errorGuardar && (
            <div className="flex items-center gap-sm text-error bg-error-container/40 rounded-xl px-md py-sm text-label-sm">
              <Icon name="error" className="text-[18px] shrink-0" fill />
              {errorGuardar}
            </div>
          )}

          <ul className="space-y-xs">
            {preguntas.map((p) => (
              <li key={p.id}>
                <label
                  className={`flex items-start gap-sm p-md rounded-xl border select-none transition-colors
                    ${bloqueada ? 'cursor-not-allowed opacity-90' : 'cursor-pointer'}
                    ${p.seleccionada
                      ? 'border-primary/40 bg-primary-fixed/30'
                      : 'border-outline-variant/40 hover:bg-surface-container-low'}`}
                >
                  <input
                    type="checkbox"
                    checked={p.seleccionada}
                    onChange={() => toggle(p.id)}
                    disabled={guardando || bloqueada}
                    className="w-4 h-4 accent-primary mt-0.5 shrink-0 disabled:cursor-not-allowed"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="text-label-md text-on-surface line-clamp-2 break-words">
                      {limpiarEnunciadoCloze(p.enunciado)}
                    </p>
                    <div className="flex items-center gap-xs mt-xs flex-wrap">
                      <Badge tone="neutral">{tipoLabel(p.tipo)}</Badge>
                      <span className="text-label-sm text-on-surface-variant tabular-nums">
                        #{p.orden}
                      </span>
                    </div>
                  </div>
                </label>
              </li>
            ))}
          </ul>

          {ningunaMarcada && !bloqueada && (
            <div className="flex items-center gap-sm text-warning bg-warning-container rounded-xl px-md py-sm text-label-sm">
              <Icon name="info" className="text-[18px] shrink-0" fill />
              Tenés que dejar al menos 1 pregunta.
            </div>
          )}

          {!bloqueada && hayCambiosSeleccion && (
            <div className="flex justify-end">
              <Button
                variant="primary"
                icon={guardando ? undefined : 'save'}
                onClick={guardar}
                disabled={guardando || ningunaMarcada}
              >
                {guardando ? 'Guardando…' : 'Guardar selección'}
              </Button>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
