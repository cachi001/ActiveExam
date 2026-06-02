import { useEffect, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Card, Stat, SectionTitle } from '../ui/components';
import { api } from '../lib/api';
import { useApp } from '../lib/store';
import { STAFF_NAV } from '../ui/nav';
import type { SesionEnVivo } from '../lib/types';
import { StudentFeedCard } from './admin/components/StudentFeedCard';
import { ProctorControls } from './admin/components/ProctorControls';

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
                  <StudentFeedCard key={s.id} sesion={s} umbral={umbral} />
                ))}
              </div>
            </Card>
          </div>

          <ProctorControls
            umbral={umbral}
            onUmbralChange={setUmbral}
            retos={retos}
            onRetosChange={setRetos}
            lista={lista}
            mensaje={mensaje}
            onMensajeChange={setMensaje}
            destinatario={destinatario}
            onDestinatarioChange={setDestinatario}
            onEnviar={enviar}
          />
        </div>
      </div>
    </StaffShell>
  );
}
