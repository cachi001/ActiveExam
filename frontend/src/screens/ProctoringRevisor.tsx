/**
 * ProctoringRevisor — Lista de sesiones grabadas del backend slim (C-46).
 *
 * Ruta: /admin/proctoring-sessions (roles: admin_examenes | coordinador | revisor)
 * Accede a GET /proctoring/sessions via api.listarSesionesProctoring() (dual real/mock).
 *
 * L2.5: este módulo NO sanciona automáticamente. El score es un indicador de
 * prioridad para revisión humana. La decisión disciplinaria es siempre del revisor.
 * Ley 25.326: no se persiste screenshot_base64 en este componente (solo se lista).
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Card } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { ConfirmModal } from '../ui/ConfirmModal';
import { RefreshBar } from '../ui/RefreshBar';
import { STAFF_NAV } from '../ui/nav';
import { useAutoRefresh } from '../lib/useAutoRefresh';
import { useToast } from '../ui/toast';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api } from '../lib/api';
import type { SesionProctoringResumen } from '../lib/types';
import { SesionCard } from './proctoring/SesionCard';
import { ResumenSesiones } from './proctoring/ResumenSesiones';
import { ListaSkeleton, ListaVacia } from './proctoring/ListaEstados';
import { GrabadasExamenGroup } from './proctoring/GrabadasExamenGroup';
import { type ExamInfo } from './proctoring/helpers';
import { examInfoDeSesion } from './proctoring/colaAgregacion';

const PROCTORING_DETAIL_ROUTE = '/admin/proctoring-session-detail';

export default function ProctoringRevisor() {
  const navigate = useNavigate();
  const toast = useToast();
  const setProctoringSessionId = useApp((s) => s.setProctoringSessionId);
  const setProctoringDetailBackRoute = useApp((s) => s.setProctoringDetailBackRoute);
  const [sesiones, setSesiones] = useState<SesionProctoringResumen[]>([]);
  const [cargando, setCargando] = useState(true);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | undefined>();
  // Sesión pendiente de confirmación de borrado (null = modal cerrado).
  const [aBorrar, setABorrar] = useState<SesionProctoringResumen | null>(null);

  const cargar = useCallback(() => {
    setCargando(true);
    api
      .listarSesionesProctoring()
      // Sesiones grabadas = solo las ya finalizadas. Las que siguen en vivo se
      // ven en "Supervisión en vivo" para no duplicar y para que esta lista sea
      // realmente histórica (criterio del proctor).
      .then((data) => { setSesiones(data.filter((s) => s.finalizada_en)); setLastUpdatedAt(Date.now()); })
      .catch(() => setSesiones([]))
      .finally(() => setCargando(false));
  }, []);

  useEffect(() => { cargar(); }, [cargar]);

  // Auto-refresh cada 5 min: aparecen sesiones a medida que se finalizan.
  useAutoRefresh(cargar, undefined, !cargando);

  const handleAbrir = (sesion: SesionProctoringResumen) => {
    setProctoringSessionId(sesion.id);
    setProctoringDetailBackRoute('/admin/proctoring-sessions');
    navigate(PROCTORING_DETAIL_ROUTE + '/' + sesion.id);
  };

  const handleConfirmarBorrado = async () => {
    if (!aBorrar) return;
    const sesion = aBorrar;
    setABorrar(null);
    const { ok } = await api.eliminarSesionProctoring(sesion.id);
    if (ok) {
      setSesiones((prev) => prev.filter((s) => s.id !== sesion.id));
      toast.success('Sesión eliminada');
    } else {
      toast.error('No se pudo eliminar la sesión');
    }
  };

  // Agrupar por examen (igual que supervisión en vivo): cada grupo es un examen
  // con sus sesiones dentro. Las sesiones sin examen vinculado caen a un grupo
  // aparte al final. Grupos y sesiones ordenados por fecha (más recientes arriba).
  const grupos = useMemo(() => {
    const map = new Map<
      string,
      { examId: string | null; examInfo: ExamInfo | null; sesiones: SesionProctoringResumen[] }
    >();
    for (const s of sesiones) {
      const key = s.exam_id ?? '__sin_examen__';
      if (!map.has(key)) {
        map.set(key, { examId: s.exam_id ?? null, examInfo: examInfoDeSesion(s), sesiones: [] });
      }
      map.get(key)!.sesiones.push(s);
    }
    const arr = [...map.values()].map((g) => ({
      ...g,
      sesiones: [...g.sesiones].sort((a, b) => b.creada_en.localeCompare(a.creada_en)),
    }));
    arr.sort((a, b) => {
      if (!a.examId && b.examId) return 1; // "sin examen" al final
      if (a.examId && !b.examId) return -1;
      return (b.sesiones[0]?.creada_en ?? '').localeCompare(a.sesiones[0]?.creada_en ?? '');
    });
    return arr;
  }, [sesiones]);

  return (
    <StaffShell
      nav={STAFF_NAV}
      title="Registro de sesiones"
      subtitle="Historial de sesiones de proctoring ya finalizadas. Para sesiones en curso, usá Supervisión en vivo; para acotar por riesgo, la Cola de revisión."
      help={
        <HelpButton title="Registro de sesiones">
          <p>
            Listado histórico de sesiones de proctoring <strong>ya finalizadas</strong>.
            Las que siguen en curso aparecen en <em>Supervisión en vivo</em>; para
            acotar por riesgo, usá <em>Cola de revisión</em>.
          </p>
          <p>
            Click en una fila para abrir el detalle con eventos, evidencia y biometría. La
            decisión disciplinaria siempre es del revisor.
          </p>
        </HelpButton>
      }
    >
      <div className="space-y-lg animate-in fade-in duration-500">
        <RefreshBar
          texto="Registro de sesiones"
          lastUpdatedAt={lastUpdatedAt}
          cargando={cargando}
          onActualizar={cargar}
        />

        {/* Resumen agregado */}
        {!cargando && sesiones.length > 0 && <ResumenSesiones sesiones={sesiones} />}

        {/* Lista agrupada por examen (colapsable), igual que supervisión en vivo.
            Sin header repetido: el título de la página ya dice "Registro de sesiones" y
            el conteo lo muestra ResumenSesiones (arriba). */}
        <div className="space-y-md">
          {cargando && <Card className="space-y-md"><ListaSkeleton /></Card>}

          {!cargando && sesiones.length === 0 && <Card><ListaVacia /></Card>}

          {!cargando && sesiones.length > 0 && (
            <div className="space-y-md">
              {grupos.map((g) => (
                <GrabadasExamenGroup
                  key={g.examId ?? '__sin_examen__'}
                  examInfo={g.examInfo}
                  count={g.sesiones.length}
                >
                  {g.sesiones.map((s) => (
                    <SesionCard
                      key={s.id}
                      sesion={s}
                      onAbrir={handleAbrir}
                      onEliminar={setABorrar}
                      examInfo={null}
                    />
                  ))}
                </GrabadasExamenGroup>
              ))}
            </div>
          )}
        </div>
      </div>

      <ConfirmModal
        abierto={aBorrar !== null}
        variante="danger"
        titulo="Eliminar sesión grabada"
        mensaje={
          <>
            Vas a eliminar{' '}
            <strong className="text-on-surface">
              {aBorrar?.etiqueta?.trim() || 'esta sesión'}
            </strong>
            . Esta acción no se puede deshacer.
          </>
        }
        textoConfirmar="Eliminar"
        textoCancelar="Cancelar"
        onConfirmar={() => void handleConfirmarBorrado()}
        onCancelar={() => setABorrar(null)}
      />
    </StaffShell>
  );
}
