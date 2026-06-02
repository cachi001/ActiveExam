import { useState, useMemo } from 'react';
import { StaffShell } from '../ui/shells';
import { Icon, Card, Button, SectionTitle, FormField, RangeInput } from '../ui/components';
import { ADMIN_NAV } from './AdminDashboard';
import { api } from '../lib/api';
import { useApp } from '../lib/store';
import { useNavigate } from '../lib/router';
import type { Examen, TipoEvento } from '../lib/types';
import { INSTITUTION } from '../config/institution';
import DetectoresSelector from './admin/components/DetectoresSelector';
import ExamenResumenCard from './admin/components/ExamenResumenCard';

export default function ConfigureExam() {
  const editando = useApp((s) => s.examenActivo);
  const navigate = useNavigate();

  const [form, setForm] = useState<Examen>(() => editando ?? {
    id: `EX-${INSTITUTION.idPrefix}-${Math.random().toString(36).slice(2, 6).toUpperCase()}`,
    nombre: '',
    catedra: '',
    estado: 'borrador',
    inicio: new Date(Date.now() + 10 * 60 * 1000).toISOString().slice(0, 16),
    duracion_min: 90,
    umbral_score: 70,
    detectores: ['rostro_ausente', 'multiples_rostros', 'mirada_desviada_sostenida', 'perdida_de_foco', 'monitor_adicional'] as TipoEvento[],
    retencion_dias: 30,
    inscriptos: 0,
    rindiendo: 0,
  });

  const [guardando, setGuardando] = useState(false);
  // Lazy validation: track which fields have been blurred by the user
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  const set = <K extends keyof Examen>(k: K, v: Examen[K]) => setForm((f) => ({ ...f, [k]: v }));
  const touch = (campo: string) => setTouched((t) => ({ ...t, [campo]: true }));

  // Derive all errors from form state (useMemo, no external state)
  const errors = useMemo<Record<string, string>>(() => {
    const e: Record<string, string> = {};

    if (!form.nombre.trim()) {
      e.nombre = 'El nombre del examen es requerido';
    }
    if (!form.catedra.trim()) {
      e.catedra = 'La cátedra es requerida';
    }
    const inicioDate = new Date(form.inicio);
    const ahora = new Date();
    if (!form.inicio || isNaN(inicioDate.getTime())) {
      e.inicio = 'Ingresá una fecha y hora de inicio válida';
    } else if (!editando && inicioDate.getTime() <= ahora.getTime() + 5 * 60 * 1000) {
      // La regla de "futuro" solo aplica al CREAR un examen nuevo; al editar uno existente se respeta su fecha.
      e.inicio = 'El inicio debe ser en el futuro';
    }
    if (form.duracion_min < 30 || form.duracion_min > 180) {
      e.duracion_min = 'La duración debe estar entre 30 y 180 minutos';
    }
    if (form.umbral_score < 30 || form.umbral_score > 90) {
      e.umbral_score = 'El umbral debe estar entre 30 y 90';
    }
    if (form.retencion_dias < 7 || form.retencion_dias > 90) {
      e.retencion_dias = 'La retención debe estar entre 7 y 90 días';
    }

    return e;
  }, [form, editando]);

  const hayErrores = Object.keys(errors).length > 0;

  // Only show an error message if the field has been touched (lazy)
  const errorVisible = (campo: string) => touched[campo] ? errors[campo] : undefined;

  const guardar = async () => {
    // Guard against invalid form (defense in depth — button already disabled)
    if (hayErrores) return;
    setGuardando(true);
    await api.saveExam({ ...form, estado: form.estado === 'borrador' ? 'programado' : form.estado });
    setGuardando(false);
    navigate('/admin/examenes');
  };

  return (
    <StaffShell nav={ADMIN_NAV} title={editando ? 'Configurar examen' : 'Crear examen'}>
      <div className="max-w-3xl space-y-lg">

        {/* Sección 1: Información del examen */}
        <Card className="space-y-md">
          <SectionTitle sub="Datos generales">Información del examen</SectionTitle>
          <FormField label="Nombre del examen" error={errorVisible('nombre')}>
            <input
              value={form.nombre}
              onChange={(e) => set('nombre', e.target.value)}
              onBlur={() => touch('nombre')}
              placeholder="Nombre del examen"
              className="w-full input"
            />
          </FormField>
          <div className="grid sm:grid-cols-2 gap-md">
            <FormField label="Cátedra" error={errorVisible('catedra')}>
              <input
                value={form.catedra}
                onChange={(e) => set('catedra', e.target.value)}
                onBlur={() => touch('catedra')}
                placeholder="Nombre de la cátedra"
                className="w-full input"
              />
            </FormField>
            <FormField label="Inicio" error={errorVisible('inicio')}>
              <input
                type="datetime-local"
                value={form.inicio.slice(0, 16)}
                onChange={(e) => set('inicio', e.target.value)}
                onBlur={() => touch('inicio')}
                className="w-full input"
              />
            </FormField>
          </div>
          <RangeInput
            label="Duración"
            unit="minutos"
            min={30}
            max={180}
            step={5}
            value={form.duracion_min}
            onChange={(v) => set('duracion_min', v)}
          />
        </Card>

        {/* Sección 2: Parámetros de proctoring */}
        <Card className="space-y-md">
          <SectionTitle sub="Política de priorización y privacidad">Parámetros de proctoring</SectionTitle>
          <RangeInput
            label="Umbral de cola de revisión"
            unit="%"
            min={30}
            max={90}
            value={form.umbral_score}
            onChange={(v) => set('umbral_score', v)}
            hint="Sesiones que superen este score al finalizar entran a revisión humana."
          />
          <FormField label="Detectores activos">
            <DetectoresSelector
              value={form.detectores}
              onChange={(d) => set('detectores', d)}
            />
          </FormField>
          <FormField
            label="Retención de evidencia (días)"
            hint="Por defecto 30 días (Ley 25.326). Luego se elimina automáticamente."
            error={errorVisible('retencion_dias')}
          >
            <input
              type="number"
              min={7}
              max={90}
              value={form.retencion_dias}
              onChange={(e) => set('retencion_dias', Number(e.target.value))}
              onBlur={() => touch('retencion_dias')}
              className="w-32 input"
            />
          </FormField>
        </Card>

        {/* Sección 3: Resumen del examen */}
        <div className="space-y-md">
          <SectionTitle sub="Revisá la configuración antes de guardar">Resumen del examen</SectionTitle>
          <ExamenResumenCard examen={form} />
        </div>

        {/* Botones de acción */}
        <div className="flex gap-sm">
          <Button variant="outline" icon="arrow_back" onClick={() => navigate('/admin/examenes')}>
            Cancelar
          </Button>
          <Button
            icon={guardando ? undefined : 'save'}
            onClick={guardar}
            disabled={hayErrores || guardando}
          >
            {guardando
              ? <span className="inline-flex items-center gap-xs"><Icon name="progress_activity" className="ae-spin text-[20px]" /> Guardando…</span>
              : 'Guardar examen'}
          </Button>
        </div>

      </div>
    </StaffShell>
  );
}
