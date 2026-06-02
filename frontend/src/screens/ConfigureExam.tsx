import { useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Icon, Card, Button, SectionTitle, FormField, RangeInput } from '../ui/components';
import { ADMIN_NAV } from './AdminDashboard';
import { TIPO_EVENTO_LABEL, api } from '../lib/api';
import { useApp } from '../lib/store';
import { useNavigate } from '../lib/router';
import type { Examen, TipoEvento } from '../lib/types';
import { INSTITUTION } from '../config/institution';

const DETECTORES: TipoEvento[] = ['rostro_ausente', 'multiples_rostros', 'mirada_desviada_sostenida', 'perdida_de_foco', 'monitor_adicional'];

export default function ConfigureExam() {
  const editando = useApp((s) => s.examenActivo);
  const navigate = useNavigate();

  const [form, setForm] = useState<Examen>(() => editando ?? {
    id: `EX-${INSTITUTION.idPrefix}-${Math.random().toString(36).slice(2, 6).toUpperCase()}`,
    nombre: '', catedra: '', estado: 'borrador', inicio: new Date().toISOString().slice(0, 16),
    duracion_min: 90, umbral_score: 70, detectores: [...DETECTORES], retencion_dias: 30, inscriptos: 0, rindiendo: 0,
  });
  const [guardando, setGuardando] = useState(false);

  const set = <K extends keyof Examen>(k: K, v: Examen[K]) => setForm((f) => ({ ...f, [k]: v }));
  const toggleDet = (d: TipoEvento) => set('detectores', form.detectores.includes(d) ? form.detectores.filter((x) => x !== d) : [...form.detectores, d]);

  const guardar = async () => {
    if (!form.nombre.trim()) { alert('Ingresá el nombre del examen.'); return; }
    setGuardando(true);
    await api.saveExam({ ...form, estado: form.estado === 'borrador' ? 'programado' : form.estado });
    setGuardando(false);
    navigate('/admin/examenes');
  };

  return (
    <StaffShell nav={ADMIN_NAV} title={editando ? 'Configurar examen' : 'Crear examen'}>
      <div className="max-w-3xl space-y-lg">
        <Card className="space-y-md">
          <SectionTitle sub="Datos generales">Información del examen</SectionTitle>
          <FormField label="Nombre del examen">
            <input value={form.nombre} onChange={(e) => set('nombre', e.target.value)} placeholder="Nombre del examen"
              className="w-full input" />
          </FormField>
          <div className="grid sm:grid-cols-2 gap-md">
            <FormField label="Cátedra">
              <input value={form.catedra} onChange={(e) => set('catedra', e.target.value)} placeholder="Nombre de la cátedra" className="w-full input" />
            </FormField>
            <FormField label="Inicio">
              <input type="datetime-local" value={form.inicio.slice(0, 16)} onChange={(e) => set('inicio', e.target.value)} className="w-full input" />
            </FormField>
          </div>
          <RangeInput label="Duración" unit="minutos" min={30} max={180} step={5} value={form.duracion_min} onChange={(v) => set('duracion_min', v)} />
        </Card>

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
            <div className="grid sm:grid-cols-2 gap-base">
              {DETECTORES.map((d) => {
                const on = form.detectores.includes(d);
                return (
                  <label key={d} className={`flex items-center gap-base p-sm rounded-xl border cursor-pointer ${on ? 'bg-primary-fixed/40 border-primary-container' : 'bg-surface-container-low border-outline-variant/40'}`}>
                    <input type="checkbox" checked={on} onChange={() => toggleDet(d)} className="accent-primary w-4 h-4" />
                    <span className="text-label-md font-semibold text-on-surface">{TIPO_EVENTO_LABEL[d]}</span>
                  </label>
                );
              })}
            </div>
          </FormField>

          <FormField label="Retención de evidencia (días)" hint="Por defecto 30 días (Ley 25.326). Luego se elimina automáticamente.">
            <input type="number" min={7} max={90} value={form.retencion_dias} onChange={(e) => set('retencion_dias', Number(e.target.value))} className="w-32 input" />
          </FormField>
        </Card>

        <div className="flex gap-sm">
          <Button variant="outline" icon="arrow_back" onClick={() => navigate('/admin/examenes')}>Cancelar</Button>
          <Button icon={guardando ? undefined : 'save'} onClick={guardar} disabled={guardando}>
            {guardando ? <span className="inline-flex items-center gap-xs"><Icon name="progress_activity" className="ae-spin text-[20px]" /> Guardando…</span> : 'Guardar examen'}
          </Button>
        </div>
      </div>
    </StaffShell>
  );
}

