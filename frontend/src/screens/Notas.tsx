/**
 * Notas — punto de entrada único para ver quién rindió y sincronizar notas,
 * sin tener que entrar al detalle de cada examen.
 *
 * Filtro en cascada Materia → Comisión → Examen, con selects SEPARADOS —
 * a propósito igual al patrón que ya usa la página "Exámenes" (`ExamList.tsx`,
 * `api.materiasDisponibles()` + `api.comisionesDeMateria()`), en vez de un
 * selector combinado: mismo filtro, misma UX, en las dos pantallas.
 *
 * Al elegir el examen se muestra ABAJO, en la misma pantalla, el mismo panel
 * de resultados que ya existía (`ResultadosExamenPanel`, compartido con
 * `/admin/examenes/:id/resultados`): sin duplicar lógica, sin endpoint nuevo.
 *
 * Ruta: /admin/notas (roles: tutor | coordinador | admin_sistema).
 */
import { useEffect, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Card, Icon, SectionTitle } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { STAFF_NAV } from '../ui/nav';
import { API_BASE } from '../lib/api';
import { authProvider } from '../lib/authProvider';
import { listarMateriasFn, listarComisionesFn, listarExamenesDeComisionFn } from '../lib/examContentBrowse';
import type { Materia, Comision, ExamenContenidoResumen } from '../lib/types';
import { ResultadosExamenPanel } from './exam-detail/ResultadosExamenPanel';

const selectClass =
  'w-full rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none disabled:bg-surface-100 disabled:text-on-surface-variant disabled:cursor-not-allowed';

export default function Notas() {
  const [materias, setMaterias] = useState<Materia[]>([]);
  const [materiaId, setMateriaId] = useState('');

  const [comisiones, setComisiones] = useState<Comision[]>([]);
  const [comisionId, setComisionId] = useState('');
  const [cargandoComisiones, setCargandoComisiones] = useState(false);

  const [examenes, setExamenes] = useState<ExamenContenidoResumen[]>([]);
  const [examenId, setExamenId] = useState('');
  const [cargandoExamenes, setCargandoExamenes] = useState(false);

  // 1. Materias, una sola vez.
  useEffect(() => {
    listarMateriasFn(API_BASE, authProvider.getToken()).then(setMaterias);
  }, []);

  // 2. Comisiones de la materia elegida.
  useEffect(() => {
    setComisionId('');
    setComisiones([]);
    setExamenId('');
    setExamenes([]);
    if (!materiaId) return;
    setCargandoComisiones(true);
    listarComisionesFn(API_BASE, authProvider.getToken(), materiaId)
      .then(setComisiones)
      .finally(() => setCargandoComisiones(false));
  }, [materiaId]);

  // 3. Exámenes de la comisión elegida.
  useEffect(() => {
    setExamenId('');
    setExamenes([]);
    if (!comisionId) return;
    setCargandoExamenes(true);
    listarExamenesDeComisionFn(API_BASE, authProvider.getToken(), comisionId)
      .then(setExamenes)
      .finally(() => setCargandoExamenes(false));
  }, [comisionId]);

  const examenElegido = examenes.find((e) => e.id === examenId) ?? null;

  return (
    <StaffShell
      nav={STAFF_NAV}
      title="Notas"
      subtitle="Elegí materia, comisión y examen para ver quién rindió y sincronizar sus notas con Moodle."
      help={
        <HelpButton title="Notas">
          <p>
            Elegí <strong>Materia</strong> → <strong>Comisión</strong> → <strong>Examen</strong> para
            ver la lista de alumnos que rindieron, sus notas y el estado de sincronización con Moodle.
          </p>
          <p>
            Es el mismo panel al que se llega desde el detalle de un examen — acá está
            accesible directo desde el menú, sin entrar examen por examen.
          </p>
        </HelpButton>
      }
    >
      <div className="space-y-lg animate-in fade-in duration-500">
        <Card>
          <SectionTitle icon="filter_alt">Elegí un examen</SectionTitle>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-md">
            <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
              Materia
              <select
                value={materiaId}
                onChange={(e) => setMateriaId(e.target.value)}
                className={selectClass}
              >
                <option value="">Seleccioná una materia…</option>
                {materias.map((m) => (
                  <option key={m.id} value={m.id}>{m.codigo} — {m.nombre}</option>
                ))}
              </select>
            </label>

            <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
              Comisión
              <select
                value={comisionId}
                onChange={(e) => setComisionId(e.target.value)}
                disabled={!materiaId || cargandoComisiones}
                className={selectClass}
              >
                <option value="">
                  {!materiaId
                    ? 'Elegí una materia primero'
                    : cargandoComisiones
                      ? 'Cargando…'
                      : comisiones.length === 0
                        ? 'Sin comisiones'
                        : 'Seleccioná una comisión…'}
                </option>
                {comisiones.map((c) => (
                  <option key={c.id} value={c.id}>{c.codigo ? `${c.codigo} — ${c.nombre}` : c.nombre}</option>
                ))}
              </select>
            </label>

            <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
              Examen
              <select
                value={examenId}
                onChange={(e) => setExamenId(e.target.value)}
                disabled={!comisionId || cargandoExamenes}
                className={selectClass}
              >
                <option value="">
                  {!comisionId
                    ? 'Elegí una comisión primero'
                    : cargandoExamenes
                      ? 'Cargando…'
                      : examenes.length === 0
                        ? 'Sin exámenes'
                        : 'Seleccioná un examen…'}
                </option>
                {examenes.map((e) => (
                  <option key={e.id} value={e.id}>{e.titulo}</option>
                ))}
              </select>
            </label>
          </div>

          {!examenId && (
            <div className="mt-md flex items-center gap-sm text-on-surface-variant bg-surface-100 rounded-xl px-md py-sm text-label-sm">
              <Icon name="info" className="text-[18px] shrink-0" />
              Elegí materia, comisión y examen para ver quién rindió.
            </div>
          )}
        </Card>

        {examenElegido && (
          <ResultadosExamenPanel key={examenElegido.id} examenId={examenElegido.id} />
        )}
      </div>
    </StaffShell>
  );
}
