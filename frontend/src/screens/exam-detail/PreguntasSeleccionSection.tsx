import { useCallback, useEffect, useState } from 'react';
import { Badge, Button, Card, Icon, SectionTitle } from '../../ui/components';
import { getPreguntasExamen, setPreguntasSeleccion, type PreguntaSeleccion } from '../../lib/examContentAdmin';

const TIPO_PREGUNTA_LABEL: Record<string, string> = {
  multichoice: 'Opción múltiple',
  truefalse: 'Verdadero / Falso',
};

function tipoLabel(tipo: string): string {
  return TIPO_PREGUNTA_LABEL[tipo] ?? tipo;
}

interface Props {
  examenId: string;
  onSeleccionGuardada: (cantidad: number) => void;
}

export function PreguntasSeleccionSection({ examenId, onSeleccionGuardada }: Props) {
  const [preguntas, setPreguntas] = useState<PreguntaSeleccion[]>([]);
  const [seleccionOriginal, setSeleccionOriginal] = useState<Record<string, boolean>>({});
  const [total, setTotal] = useState(0);
  const [bloqueada, setBloqueada] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState<string | null>(null);

  const [guardando, setGuardando] = useState(false);
  const [okGuardado, setOkGuardado] = useState(false);
  const [errorGuardar, setErrorGuardar] = useState<string | null>(null);

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

  return (
    <Card>
      <SectionTitle
        sub={
          cargando
            ? 'Cargando preguntas…'
            : errorCarga
              ? undefined
              : `${seleccionadas} de ${total} pregunta${total !== 1 ? 's' : ''} seleccionada${seleccionadas !== 1 ? 's' : ''}`
        }
        action={
          !cargando && !errorCarga && preguntas.length > 0 && !bloqueada ? (
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

      {!cargando && !errorCarga && preguntas.length > 0 && (
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
                      {p.enunciado}
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
