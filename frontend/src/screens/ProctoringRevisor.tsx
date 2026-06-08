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

import { useEffect, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Icon, Card, SectionTitle } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { ConfirmModal } from '../ui/ConfirmModal';
import { STAFF_NAV } from '../ui/nav';
import { useToast } from '../ui/toast';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api } from '../lib/api';
import type { SesionProctoringResumen } from '../lib/types';
import { SesionCard } from './proctoring/SesionCard';
import { ResumenSesiones } from './proctoring/ResumenSesiones';
import { ListaSkeleton, ListaVacia } from './proctoring/ListaEstados';
import { joinExamInfo } from './proctoring/helpers';

const PROCTORING_DETAIL_ROUTE = '/admin/proctoring-session-detail';

export default function ProctoringRevisor() {
  const navigate = useNavigate();
  const toast = useToast();
  const setProctoringSessionId = useApp((s) => s.setProctoringSessionId);
  const [sesiones, setSesiones] = useState<SesionProctoringResumen[]>([]);
  const [cargando, setCargando] = useState(true);
  // Sesión pendiente de confirmación de borrado (null = modal cerrado).
  const [aBorrar, setABorrar] = useState<SesionProctoringResumen | null>(null);

  useEffect(() => {
    setCargando(true);
    api
      .listarSesionesProctoring()
      .then((data) => setSesiones(data))
      .catch(() => setSesiones([]))
      .finally(() => setCargando(false));
  }, []);

  const handleAbrir = (sesion: SesionProctoringResumen) => {
    setProctoringSessionId(sesion.id);
    navigate(PROCTORING_DETAIL_ROUTE);
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

  return (
    <StaffShell nav={STAFF_NAV} title="Sesiones grabadas">
      <div className="space-y-lg animate-in fade-in duration-500">
        {/* Header */}
        <div className="flex items-start justify-between gap-md flex-wrap">
          <div>
            <div className="flex items-center gap-sm">
              <h1 className="font-headline text-headline-md text-on-surface tracking-tight">
                Sesiones de proctoring
              </h1>
              <HelpButton title="Sesiones grabadas">
                <p>
                  Listado <strong>completo</strong> de sesiones de proctoring registradas (en vivo o
                  finalizadas), sin filtro de riesgo. Para acotar a sesiones con score alto usá
                  <em> Cola de revisión</em>.
                </p>
                <p>
                  Click en una fila para abrir el detalle con eventos, evidencia y biometría. La
                  decisión disciplinaria siempre es del revisor (L2.5).
                </p>
              </HelpButton>
            </div>
            <p className="text-body-md text-on-surface-variant mt-base">
              Historial completo de sesiones de proctoring — todas las grabadas, sin filtro.
              Para revisar solo las de alto riesgo, usá la Cola de revisión.
            </p>
          </div>
          <div className="flex items-center gap-base px-sm py-base rounded-lg bg-primary-fixed/50
            border border-primary/20 text-label-sm text-on-primary-fixed-variant">
            <Icon name="shield" className="text-[16px] shrink-0" fill />
            <span>Decisión humana</span>
          </div>
        </div>

        {/* Resumen agregado */}
        {!cargando && sesiones.length > 0 && <ResumenSesiones sesiones={sesiones} />}

        {/* Lista */}
        <Card className="space-y-md">
          <SectionTitle
            sub={cargando ? 'Cargando…' : `${sesiones.length} sesión${sesiones.length !== 1 ? 'es' : ''}`}
          >
            Sesiones grabadas
          </SectionTitle>

          {cargando && <ListaSkeleton />}

          {!cargando && sesiones.length === 0 && <ListaVacia />}

          {!cargando && sesiones.length > 0 && (
            <div className="space-y-sm">
              {sesiones.map((s) => (
                <SesionCard
                  key={s.id}
                  sesion={s}
                  onAbrir={handleAbrir}
                  onEliminar={setABorrar}
                  examInfo={joinExamInfo(s.exam_id)}
                />
              ))}
            </div>
          )}
        </Card>
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
