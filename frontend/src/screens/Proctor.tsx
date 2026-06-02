import { useEffect, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Icon, Button, Card, Stat, ScoreChip, SectionTitle } from '../ui/components';
import { DESAFIOS } from '../lib/api';
import { api } from '../lib/api';
import { useApp } from '../lib/store';
import { STAFF_NAV } from '../ui/nav';
import type { SesionEnVivo } from '../lib/types';

export const PROCTOR_NAV = STAFF_NAV;

export default function Proctor() {
  const [sesiones, setSesiones] = useState<SesionEnVivo[]>([]);
  const [umbral, setUmbral] = useState(70);
  const [retos, setRetos] = useState<string[]>(['girar_izquierda', 'sonreir', 'parpadear']);
  const [destinatario, setDestinatario] = useState('');
  const [mensaje, setMensaje] = useState('');
  const scorePropio = useApp((s) => s.scorePropio);
  const anomaliasPropias = useApp((s) => s.anomaliasVivo);

  useEffect(() => { api.liveSessions().then(setSesiones); }, []);

  // refleja en vivo la sesión "propia" (la del estudiante que está rindiendo en otra pestaña/flujo demo)
  const lista = sesiones.map((s) => s.es_propia ? { ...s, score: scorePropio, anomalias: anomaliasPropias.length } : s);
  const criticas = lista.filter((s) => s.score >= umbral).length;

  const enviar = () => {
    if (!mensaje.trim()) return;
    alert(`Mensaje correctivo cifrado enviado a ${destinatario || lista[0]?.estudiante}.`);
    setMensaje('');
  };

  return (
    <StaffShell nav={PROCTOR_NAV} title="Supervisión en vivo">
      <div className="space-y-lg">
        <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-lg">
          <Stat icon="quiz" label="Examen activo" value="Anatomía I" sub="Cátedra B · Aula virtual 104" />
          <Stat icon="tune" label="Umbral de alerta" value={`${umbral}%`} sub="Filtra sesiones de riesgo" />
          <Stat icon="groups" label="Rindiendo" value={lista.length} sub="cámaras activas (análisis local)" />
          <Stat icon="priority_high" label="Sesiones críticas" value={criticas} sub="Requieren atención" />
        </div>

        <div className="grid lg:grid-cols-3 gap-lg">
          <div className="lg:col-span-2">
            <Card>
              <SectionTitle sub="Análisis de visión local en cada equipo; el servidor re-infiere las señales."
                action={<span className="inline-flex items-center gap-base bg-success-container text-success px-sm py-base rounded-full text-label-sm font-semibold"><span className="w-2 h-2 rounded-full bg-success animate-ping" /> {lista.length} feeds en vivo</span>}>
                Mural de monitoreo
              </SectionTitle>
              <div className="grid sm:grid-cols-2 gap-md">
                {lista.map((s) => (
                  <div key={s.id} className={`rounded-xl overflow-hidden border bg-inverse-surface relative aspect-video ${s.score >= umbral ? 'border-error shadow-card' : 'border-outline-variant/40'}`}>
                    <img src={s.foto} alt={s.estudiante} className="w-full h-full object-cover opacity-80" />
                    <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent flex flex-col justify-between p-sm text-white">
                      <div className="flex items-start justify-between">
                        <span className="bg-black/50 backdrop-blur px-sm py-base rounded-full text-[10px] font-bold">{s.estudiante}</span>
                        <ScoreChip score={s.score} umbral={umbral} />
                      </div>
                      <div className="flex items-center justify-between text-[10px]">
                        <span className="inline-flex items-center gap-base"><Icon name="sensors" className="text-[12px]" /> {s.ultima_senal}</span>
                        <span className="opacity-80">{s.legajo}</span>
                      </div>
                    </div>
                    {s.estado === 'escalado' && <span className="absolute top-2 left-2 bg-error text-on-error text-[9px] font-bold px-1.5 py-0.5 rounded uppercase">Escalado</span>}
                  </div>
                ))}
              </div>
            </Card>
          </div>

          <div className="space-y-lg">
            <Card className="space-y-md">
              <h3 className="text-label-md font-bold text-on-surface border-b border-outline-variant/40 pb-base">Controles de proctoring</h3>
              <div className="space-y-base">
                <div className="flex justify-between text-label-sm font-semibold text-on-surface-variant">
                  <span>Umbral de cola de revisión</span><span>{umbral}%</span>
                </div>
                <input type="range" min={30} max={90} value={umbral} onChange={(e) => setUmbral(Number(e.target.value))} className="w-full accent-[#5b5bd6]" />
                <p className="text-label-sm text-on-surface-variant">Si un estudiante supera este score al terminar, entra automáticamente a revisión humana.</p>
              </div>
              <div className="space-y-base">
                <label className="text-label-sm uppercase tracking-wide text-on-surface-variant font-semibold">Retos activos pre-examen</label>
                <div className="grid grid-cols-2 gap-base">
                  {DESAFIOS.slice(0, 4).map((d) => {
                    const on = retos.includes(d.id);
                    return (
                      <label key={d.id} className="flex items-center gap-base p-base rounded-lg bg-surface-container-low border border-outline-variant/40 cursor-pointer text-label-sm">
                        <input type="checkbox" checked={on} className="accent-[#5b5bd6]"
                          onChange={(e) => setRetos((r) => e.target.checked ? [...r, d.id] : r.filter((x) => x !== d.id))} />
                        <span className="font-semibold">{d.label}</span>
                      </label>
                    );
                  })}
                </div>
              </div>
            </Card>

            <Card className="space-y-sm">
              <h3 className="text-label-md font-bold text-on-surface border-b border-outline-variant/40 pb-base">Mensaje correctivo</h3>
              <select value={destinatario} onChange={(e) => setDestinatario(e.target.value)}
                className="w-full text-label-md bg-surface-container-low border border-outline-variant rounded-xl px-sm py-base font-semibold outline-none">
                {lista.map((s) => <option key={s.id} value={s.estudiante}>{s.estudiante} (Riesgo {s.score}%)</option>)}
              </select>
              <textarea rows={3} value={mensaje} onChange={(e) => setMensaje(e.target.value)} placeholder="Escribí un mensaje para el estudiante…"
                className="w-full text-label-md bg-surface-container-low border border-outline-variant rounded-xl px-sm py-base outline-none focus:border-primary-container" />
              <Button variant="secondary" icon="shield" onClick={enviar} className="w-full">Enviar advertencia cifrada</Button>
            </Card>
          </div>
        </div>
      </div>
    </StaffShell>
  );
}
