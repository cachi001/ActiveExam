/**
 * SeccionProctoring — parámetros generales del examen (default del sistema).
 *
 * Cableada al endpoint real PATCH /api/v1/config (admin_sistema + MFA).
 * Carga la config efectiva al montar para pre-popular los campos.
 * Invalida el cache local de config efectiva tras guardar.
 *
 * Nota (c-68): la retención de evidencia se quitó de esta UI por pedido del
 * dueño. El backend conserva su default (inofensivo); acá no se envía.
 *
 * C-68 UX: dirty-aware footer (Guardar/Cancelar solo cuando hay cambios).
 */
import { useState, useEffect, useCallback } from 'react';
import { Card, SectionTitle, Button, Icon } from '../../ui/components';
import { useToast } from '../../ui/toast';
import DetectoresSelector from '../admin/components/DetectoresSelector';
import { api } from '../../lib/api';
import { resetEffectiveConfigCache } from '../../config/effectiveConfigCache';
import type { TipoEvento } from '../../lib/types';

const DETECTORES_DEFAULT: TipoEvento[] = [
  'rostro_ausente', 'multiples_rostros', 'mirada_desviada_sostenida', 'perdida_de_foco', 'monitor_adicional',
];

// Piso de producto (decisión del owner): el umbral de revisión NO baja de 70.
// El backend lo valida server-side (Field ge=70); acá el slider ni deja elegir menos.
const UMBRAL_MIN = 70;
const UMBRAL_MAX = 90;

interface Estado {
  umbral: number;
  detectores: TipoEvento[];
  // C-69 admin-sync: interruptores de los canales del alumno.
  chatHabilitado: boolean;
  pausasHabilitadas: boolean;
  // C-69: límite de duración de la pausa autorizada (minutos).
  pausaMaxMin: number;
}

function estadosIguales(a: Estado, b: Estado): boolean {
  return a.umbral === b.umbral &&
    a.chatHabilitado === b.chatHabilitado &&
    a.pausasHabilitadas === b.pausasHabilitadas &&
    a.pausaMaxMin === b.pausaMaxMin &&
    a.detectores.length === b.detectores.length &&
    a.detectores.every((d) => b.detectores.includes(d));
}

const ESTADO_DEFAULT: Estado = {
  umbral: 70,
  detectores: DETECTORES_DEFAULT,
  chatHabilitado: false,
  pausasHabilitadas: false,
  pausaMaxMin: 10,
};

export default function SeccionProctoring() {
  const toast = useToast();
  const [estado, setEstado] = useState<Estado>(ESTADO_DEFAULT);
  const [inicial, setInicial] = useState<Estado>(ESTADO_DEFAULT);
  const [guardando, setGuardando] = useState(false);
  const [cargando, setCargando] = useState(true);

  // Cargar config efectiva al montar para pre-popular los valores actuales.
  useEffect(() => {
    api.obtenerConfigEfectiva()
      .then((cfg) => {
        const cargado: Estado = {
          umbral: cfg.umbral_cola_revision,
          detectores: cfg.detectores_activos as TipoEvento[],
          // Degradación segura: si el backend no los manda, se asumen desactivados.
          chatHabilitado: cfg.chat_habilitado ?? false,
          pausasHabilitadas: cfg.pausas_habilitadas ?? false,
          pausaMaxMin: cfg.pausa_max_min ?? 10,
        };
        setEstado(cargado);
        setInicial(cargado);
      })
      .catch((e) => toast.error(`No se pudo cargar la configuración: ${e instanceof Error ? e.message : String(e)}`))
      .finally(() => setCargando(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const dirty = !estadosIguales(estado, inicial);

  const cancelar = useCallback(() => setEstado(inicial), [inicial]);

  async function guardar() {
    setGuardando(true);
    try {
      await api.editarConfigSistema({
        umbral_cola_revision: estado.umbral,
        detectores_activos: estado.detectores,
        chat_habilitado: estado.chatHabilitado,
        pausas_habilitadas: estado.pausasHabilitadas,
        pausa_max_min: estado.pausaMaxMin,
      });
      // Invalida el cache de config efectiva para que el examen y el harness
      // carguen la nueva config en la próxima sesión (task 4.5).
      resetEffectiveConfigCache();
      setInicial(estado);
      toast.success('Parámetros generales guardados');
    } catch (e) {
      toast.error(`Error al guardar: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setGuardando(false);
    }
  }

  if (cargando) {
    return (
      <div className="space-y-lg max-w-4xl">
        <div className="h-[200px] rounded-2xl border border-outline-variant/40 bg-white animate-pulse" />
      </div>
    );
  }

  const umbralPct = ((estado.umbral - UMBRAL_MIN) / (UMBRAL_MAX - UMBRAL_MIN)) * 100;

  return (
    <div className="space-y-lg">
      {/* Encabezado editorial: título con peso + descripción + divisor. */}
      <div className="pb-4 border-b border-outline-variant/40">
        <h2 className="font-headline text-[24px] font-bold text-on-surface tracking-tight leading-tight">Parámetros generales</h2>
        <p className="text-[13.5px] text-on-surface-variant leading-relaxed max-w-2xl mt-2">
          Definí el comportamiento por defecto del examen: a partir de qué puntaje una sesión
          entra a revisión humana, qué detectores se vigilan y qué canales de comunicación
          tiene el alumno mientras rinde.
        </p>
      </div>
      {/* items-stretch: las dos columnas quedan igualadas en alto aunque a los
          detectores les sobre espacio (se equiparan con la columna derecha). */}
      <div className="grid lg:grid-cols-3 gap-lg items-stretch">
        {/* Columna DERECHA (order-2): umbral + canales del alumno apilados. En
            desktop van a la derecha; los detectores ocupan los 2/3 de la izquierda. */}
        <div className="lg:col-span-1 lg:order-2 space-y-lg min-w-0">
        <Card className="space-y-md min-w-0 flex flex-col">
          <SectionTitle sub="A partir de qué puntaje de riesgo una sesión entra a revisión humana">
            Umbral de revisión
          </SectionTitle>

          {/* Slider moderno: valor grande + track/thumb estilados con tokens */}
          <div className="flex items-baseline gap-2">
            <span className="text-[40px] leading-none font-headline font-bold text-on-surface tabular-nums">
              {estado.umbral}
            </span>
            <span className="text-title-md font-semibold text-on-surface-variant">puntos</span>
          </div>

          <div className="relative pt-1">
            <input
              type="range"
              min={UMBRAL_MIN}
              max={UMBRAL_MAX}
              value={estado.umbral}
              onChange={(e) => setEstado((p) => ({ ...p, umbral: Number(e.target.value) }))}
              aria-label="Umbral de cola de revisión"
              aria-valuetext={`score mayor o igual a ${estado.umbral} puntos entra a la cola de revisión`}
              className="ae-slider w-full appearance-none bg-transparent cursor-pointer"
              style={{
                background: `linear-gradient(to right, #2563eb 0%, #2563eb ${umbralPct}%, #cbd5e1 ${umbralPct}%, #cbd5e1 100%)`,
              }}
            />
            <div className="flex justify-between text-[11px] text-on-surface-variant mt-1 tabular-nums">
              <span>{UMBRAL_MIN}</span>
              <span>{UMBRAL_MAX}</span>
            </div>
            <p className="text-[12px] text-on-surface mt-2 font-medium">
              Las sesiones que alcancen <strong>{estado.umbral} puntos o más</strong> entran a la cola de revisión humana.
            </p>
          </div>

          <p className="text-[12px] text-on-surface-variant leading-relaxed border-t border-outline-variant/40 pt-sm">
            El score de riesgo es un puntaje acumulado por los eventos detectados durante el examen
            (no es un porcentaje). Cuando una sesión termina con un score <strong>mayor o igual al
            valor configurado</strong>, queda marcada para que una persona la revise. Bajar el umbral
            envía más sesiones a revisión; subirlo deja solo las más sospechosas. El sistema nunca
            sanciona solo.
          </p>
        </Card>

        {/* Canales del alumno — debajo del umbral, en la columna izquierda. */}
        <Card className="space-y-md min-w-0">
          <SectionTitle sub="Qué herramientas de comunicación y ayuda tiene el alumno mientras rinde">
            Canales del alumno
          </SectionTitle>
          <div className="grid grid-cols-1 gap-2">
            <ToggleRow
              label="Chat entre proctor y alumno"
              description="Habilita el canal de mensajes en vivo entre el alumno que rinde y el proctor que supervisa. Si lo desactivás, no aparece el chat ni del lado del alumno ni del proctor."
              on={estado.chatHabilitado}
              onToggle={() => setEstado((p) => ({ ...p, chatHabilitado: !p.chatHabilitado }))}
            />
            <ToggleRow
              label="Pausas solicitadas por el alumno"
              description="Permite que el alumno pida una pausa durante el examen para que el proctor la autorice. Si lo desactivás, el alumno no ve el botón de pausa y el proctor no recibe solicitudes."
              on={estado.pausasHabilitadas}
              onToggle={() => setEstado((p) => ({ ...p, pausasHabilitadas: !p.pausasHabilitadas }))}
            />
            {estado.pausasHabilitadas && (
              <div className="flex items-center justify-between gap-3 px-4 py-3 rounded-xl border border-outline-variant/60 bg-surface-container-low/50">
                <div className="min-w-0">
                  <p className="text-label-md font-semibold text-on-surface">Duración máxima de la pausa</p>
                  <p className="text-[11px] text-on-surface-variant leading-snug mt-0.5">
                    Al vencer, el examen se reanuda solo (evita usar la pausa para hacer tiempo).
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <input
                    type="number"
                    min={1}
                    max={120}
                    inputMode="numeric"
                    aria-label="Duración máxima de la pausa en minutos"
                    disabled={guardando}
                    value={estado.pausaMaxMin}
                    onChange={(e) => setEstado((p) => ({ ...p, pausaMaxMin: Math.max(1, Math.min(120, Number(e.target.value) || 1)) }))}
                    className="w-20 text-[14px] px-3 py-2 rounded-lg border border-outline-variant bg-white focus:outline-none focus:border-surface-500"
                  />
                  <span className="text-label-sm text-on-surface-variant">min</span>
                </div>
              </div>
            )}
          </div>
        </Card>
        </div>

        {/* Detectores — 2/3 del ancho a la IZQUIERDA (order-1), en 2 columnas. */}
        <Card className="lg:col-span-2 lg:order-1 h-full space-y-md min-w-0 flex flex-col">
          <SectionTitle sub="Qué situaciones vigila el sistema por defecto durante el examen">
            Detectores activos
          </SectionTitle>
          <DetectoresSelector
            value={estado.detectores}
            onChange={(detectores) => setEstado((p) => ({ ...p, detectores }))}
          />
        </Card>
      </div>

      {/* C: Footer dirty-aware */}
      {dirty && (
        <div className="flex items-center justify-between gap-sm pt-sm border-t border-outline-variant/40">
          <div className="flex items-center gap-xs text-[12px] text-on-surface-variant">
            <Icon name="edit" className="text-[14px]" />
            Hay cambios sin guardar
          </div>
          <div className="flex gap-sm">
            <Button variant="outline" icon="undo" onClick={cancelar} disabled={guardando}>
              Cancelar
            </Button>
            <Button variant="primary" icon="save" onClick={guardar} disabled={guardando}>
              {guardando ? 'Guardando…' : 'Guardar parámetros'}
            </Button>
          </div>
        </div>
      )}

    </div>
  );
}

/**
 * ToggleRow — fila con nombre + descripción a la izquierda y un switch a la
 * derecha.
 *
 * El CONTENEDOR es neutro y el estado lo lleva SOLO el switch. Antes la tarjeta
 * entera se teñía (verde = activo / rojo = inactivo) y con nueve detectores en
 * grilla el resultado era un muro de color: el ojo no encontraba dónde mirar y el
 * rojo leía como "error" cuando apagar un detector es una decisión legítima. Con
 * el contenedor neutro, lo que salta a la vista es justamente lo excepcional — el
 * detector apagado — en vez de los ocho que están bien.
 */
function ToggleRow({
  label,
  description,
  on,
  onToggle,
}: {
  label: string;
  description: string;
  on: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={`${label} — ${on ? 'activado' : 'desactivado'}`}
      onClick={onToggle}
      className={`group flex items-center gap-3 px-4 py-3 rounded-md border text-left transition-colors min-w-0 focus:outline-none focus:ring-2 focus:ring-outline-variant ${
        on
          ? 'bg-surface-container-lowest border-outline-variant hover:border-outline'
          : 'bg-surface-container-low border-outline-variant'
      }`}
    >
      <div className="flex-1 min-w-0">
        <p className={`text-label-md font-semibold ${on ? 'text-on-surface' : 'text-on-surface-variant'}`}>
          {label}
        </p>
        <p className="text-[11px] text-on-surface-variant leading-snug mt-0.5">{description}</p>
      </div>
      <span
        className={`relative shrink-0 inline-flex h-6 w-11 rounded-full border-2 border-transparent transition-colors duration-200 ${
          on ? 'bg-success-600' : 'bg-outline'
        }`}
      >
        <span
          className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow transition-transform duration-200 ${
            on ? 'translate-x-5' : 'translate-x-0'
          }`}
        />
      </span>
    </button>
  );
}
