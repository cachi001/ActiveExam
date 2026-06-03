/**
 * Proctor — Supervisión EN VIVO de sesiones de proctoring (conectada al backend).
 *
 * Ruta: /proctor (nav: "Supervisión en vivo"). Sondea el backend slim cada
 * POLL_MS vía api.listarSesionesProctoring() (dual real/mock) y muestra las
 * sesiones ordenadas por score descendente: las de mayor riesgo, arriba.
 *
 * Tiempo real por polling: setInterval con cleanup en el unmount (sin acumular
 * timers). Degradación silenciosa: si un refresh falla, se muestra un toast pero
 * el loop sigue vivo y se mantiene la última data visible.
 *
 * L2.5: el score PRIORIZA para revisión humana, nunca sanciona. Click en una
 * sesión abre su detalle para la decisión humana asíncrona.
 * Ley 25.326: este panel solo lista metadatos agregados; no toca screenshots.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Card, Button, Icon, SectionTitle } from '../ui/components';
import { STAFF_NAV } from '../ui/nav';
import { useToast } from '../ui/toast';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api } from '../lib/api';
import type { SesionProctoringResumen } from '../lib/types';
import { SesionVivoCard } from './proctoring/SesionVivoCard';
import { ResumenVivo } from './proctoring/ResumenVivo';
import { ListaSkeleton, ListaVaciaVivo } from './proctoring/ListaEstados';
import { IndicadorVivo } from './proctoring/IndicadorVivo';

export const PROCTOR_NAV = STAFF_NAV;

/** Intervalo de polling del panel en vivo (ms). */
const POLL_MS = 4000;
const PROCTORING_DETAIL_ROUTE = '/admin/proctoring-session-detail';

/** Ordena por score desc (mayor riesgo arriba); desempata por más eventos. */
function ordenarPorRiesgo(sesiones: SesionProctoringResumen[]): SesionProctoringResumen[] {
  return [...sesiones].sort(
    (a, b) => b.score - a.score || b.total_eventos - a.total_eventos,
  );
}

export default function Proctor() {
  const navigate = useNavigate();
  const toast = useToast();
  const setProctoringSessionId = useApp((s) => s.setProctoringSessionId);

  const [sesiones, setSesiones] = useState<SesionProctoringResumen[]>([]);
  const [cargaInicial, setCargaInicial] = useState(true);
  const [refrescando, setRefrescando] = useState(false);
  const [ultimoRefresh, setUltimoRefresh] = useState<number | null>(null);

  // Evita refrescos solapados (el manual y el del intervalo) y stale closures.
  const enVuelo = useRef(false);
  const toastRef = useRef(toast);
  toastRef.current = toast;

  const refrescar = useCallback(async (manual: boolean) => {
    if (enVuelo.current) return;
    enVuelo.current = true;
    if (manual) setRefrescando(true);
    try {
      const data = await api.listarSesionesProctoring();
      setSesiones(ordenarPorRiesgo(data));
      setUltimoRefresh(Date.now());
    } catch {
      // Degradación silenciosa: avisamos pero NO rompemos el loop ni borramos
      // la última data visible. El próximo tick reintenta solo.
      toastRef.current.error('No se pudieron actualizar las sesiones en vivo');
    } finally {
      enVuelo.current = false;
      if (manual) setRefrescando(false);
      setCargaInicial(false);
    }
  }, []);

  // Polling con cleanup: una sola carga inicial + un único intervalo que se
  // limpia en el unmount (sin acumular timers entre renders).
  useEffect(() => {
    void refrescar(false);
    const id = setInterval(() => void refrescar(false), POLL_MS);
    return () => clearInterval(id);
  }, [refrescar]);

  const handleAbrir = (sesion: SesionProctoringResumen) => {
    setProctoringSessionId(sesion.id);
    navigate(PROCTORING_DETAIL_ROUTE);
  };

  return (
    <StaffShell nav={PROCTOR_NAV} title="Supervisión en vivo">
      <div className="space-y-lg animate-in fade-in duration-500">
        {/* Header: título + indicador en vivo + refresco manual */}
        <div className="flex items-start justify-between gap-md flex-wrap">
          <div>
            <h1 className="font-headline text-headline-md text-on-surface tracking-tight">
              Supervisión en vivo
            </h1>
            <p className="text-body-md text-on-surface-variant mt-base">
              Sesiones de proctoring activas, ordenadas por riesgo. El score prioriza
              para revisión humana; nunca sanciona.
            </p>
          </div>
          <div className="flex items-center gap-sm">
            <IndicadorVivo ultimoRefresh={ultimoRefresh} activo={!refrescando} />
            <Button
              variant="outline"
              size="sm"
              icon="refresh"
              onClick={() => void refrescar(true)}
              disabled={refrescando}
            >
              {refrescando ? 'Actualizando…' : 'Actualizar'}
            </Button>
          </div>
        </div>

        {/* Resumen agregado del lote actual */}
        {!cargaInicial && sesiones.length > 0 && <ResumenVivo sesiones={sesiones} />}

        {/* Lista de sesiones en vivo */}
        <Card className="space-y-md">
          <SectionTitle
            sub={
              cargaInicial
                ? 'Conectando…'
                : `${sesiones.length} sesión${sesiones.length !== 1 ? 'es' : ''} en vivo`
            }
            action={
              <span className="inline-flex items-center gap-base text-label-sm text-on-surface-variant">
                <Icon name="bolt" className="text-[16px]" />
                actualiza cada {POLL_MS / 1000}s
              </span>
            }
          >
            Mural de monitoreo
          </SectionTitle>

          {cargaInicial && <ListaSkeleton />}

          {!cargaInicial && sesiones.length === 0 && <ListaVaciaVivo />}

          {!cargaInicial && sesiones.length > 0 && (
            <div className="space-y-sm">
              {sesiones.map((s) => (
                <SesionVivoCard key={s.id} sesion={s} onAbrir={handleAbrir} />
              ))}
            </div>
          )}
        </Card>
      </div>
    </StaffShell>
  );
}
