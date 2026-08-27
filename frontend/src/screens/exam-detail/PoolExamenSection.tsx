/**
 * PoolExamenSection — todas las preguntas de un examen SORTEADO, en solo lectura.
 *
 * En un examen sorteado no hay nada que tildar: qué preguntas le tocan a cada
 * alumno se resuelve cuando entra. Pero el docente igual necesita **ver el
 * conjunto completo** del que se sortea, para revisar que su examen quedó bien
 * armado antes de habilitarlo.
 *
 * Antes esa lista solo existía dentro de la pantalla de selección manual. Al
 * sacarla de los exámenes sorteados (donde prometía "0 de 30 seleccionadas" y
 * confundía), el docente se quedó sin ninguna forma de ver sus preguntas. Esta
 * sección cubre ese hueco sin traer de vuelta los controles que no aplican.
 *
 * D3: los enunciados se limpian con `limpiarEnunciadoCloze`. La sintaxis cloze
 * embebe la respuesta correcta y el feedback de cada opción; volcarla cruda haría
 * ilegible la lista y expondría las soluciones en pantalla.
 */
import { useCallback, useEffect, useState } from 'react';
import { Button, Card, Icon, LoadingSpinner, SectionTitle } from '../../ui/components';
import { Pagination, PageSizeSelect } from '../../ui/Pagination';
import { getPreguntasExamen, type PreguntaSeleccion } from '../../lib/examContentAdmin';
import { limpiarEnunciadoCloze } from '../../lib/cloze';

const POR_PAGINA_DEFAULT = 10;
const OPCIONES_POR_PAGINA = [10, 20, 50];

export function PoolExamenSection({ examenId }: { examenId: string }) {
  const [preguntas, setPreguntas] = useState<PreguntaSeleccion[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pagina, setPagina] = useState(1);
  const [tamPagina, setTamPagina] = useState(POR_PAGINA_DEFAULT);

  const cargar = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      const resp = await getPreguntasExamen(examenId);
      setPreguntas(resp.items);
      setPagina(1);
    } catch (err: unknown) {
      // D16: un fallo de carga NO se dibuja como "el examen no tiene preguntas".
      setError(err instanceof Error ? err.message : 'No se pudieron cargar las preguntas.');
      setPreguntas([]);
    } finally {
      setCargando(false);
    }
  }, [examenId]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const totalPaginas = Math.max(1, Math.ceil(preguntas.length / tamPagina));
  const paginaActual = Math.min(pagina, totalPaginas);
  const visibles = preguntas.slice((paginaActual - 1) * tamPagina, paginaActual * tamPagina);

  return (
    <Card>
      <SectionTitle
        icon="checklist"
        sub={
          cargando
            ? 'Cargando preguntas…'
            : error
              ? undefined
              : `${preguntas.length} pregunta${preguntas.length !== 1 ? 's' : ''} en total. De acá se sortean las de cada alumno.`
        }
        action={
          !cargando && !error && preguntas.length > 0 ? (
            <PageSizeSelect
              value={tamPagina}
              onChange={(n) => {
                setTamPagina(n);
                setPagina(1);
              }}
              options={OPCIONES_POR_PAGINA}
            />
          ) : undefined
        }
      >
        Preguntas de este examen
      </SectionTitle>

      {cargando && <LoadingSpinner size="sm" label="Cargando preguntas…" />}

      {!cargando && error && (
        <div className="space-y-md">
          <div className="flex items-center gap-sm text-error bg-error-container/40 rounded-xl px-md py-sm text-label-sm">
            <Icon name="error" className="text-[18px] shrink-0" fill />
            {error}
          </div>
          <Button variant="outline" size="sm" icon="refresh" onClick={cargar}>
            Reintentar
          </Button>
        </div>
      )}

      {!cargando && !error && preguntas.length === 0 && (
        <div className="flex flex-col items-center justify-center py-xl text-on-surface-variant gap-2">
          <Icon name="quiz" className="text-[40px] text-outline" />
          <p className="text-label-md">
            Este examen todavía no tiene preguntas copiadas del banco.
          </p>
        </div>
      )}

      {!cargando && !error && preguntas.length > 0 && (
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-2">
            {visibles.map((p, i) => {
              const numero = (paginaActual - 1) * tamPagina + i + 1;
              const texto = limpiarEnunciadoCloze(p.enunciado) || '(sin enunciado)';
              return (
                <div
                  key={p.id}
                  className="flex items-start gap-3 px-4 py-3 rounded-xl border border-outline-variant/40 bg-surface-container-lowest"
                >
                  <span className="shrink-0 w-7 h-7 rounded-lg bg-surface-200 text-on-surface-variant flex items-center justify-center text-label-sm font-medium tabular-nums">
                    {numero}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-label-md text-on-surface" title={texto}>
                      {texto}
                    </p>
                    <p className="text-label-sm text-on-surface-variant mt-0.5">{p.tipo}</p>
                  </div>
                </div>
              );
            })}
          </div>

          <Pagination
            currentPage={paginaActual}
            totalPages={totalPaginas}
            totalElements={preguntas.length}
            pageSize={tamPagina}
            onPageChange={setPagina}
          />
        </div>
      )}
    </Card>
  );
}
