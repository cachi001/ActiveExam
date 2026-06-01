import { useEffect, useState } from 'react';
import { StudentShell } from '../ui/shells';
import { Icon, Button, Card } from '../ui/components';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api } from '../lib/api';
import { Term } from '../ui/Term';
import type { ConsentTextResponse } from '../lib/types';

export default function Consent() {
  const navigate = useNavigate();
  const examen = useApp((s) => s.examenActivo);
  const [texto, setTexto] = useState<ConsentTextResponse | null>(null);
  const [acepto, setAcepto] = useState(false); // RN-CO-02: nunca pre-marcado
  const [guardando, setGuardando] = useState(false);

  useEffect(() => { api.getConsentText().then(setTexto); }, []);

  const aceptar = async () => {
    if (!acepto || !examen) return;
    setGuardando(true);
    await api.recordConsent(examen.id);
    setGuardando(false);
    navigate('/biometria');
  };

  const alternativa = () => {
    alert('Se escala tu caso a un proctor. Se te asignará una vía alternativa sin biometría para rendir.');
    navigate('/sala-espera');
  };

  return (
    <StudentShell step={2}>
      <div className="max-w-3xl mx-auto space-y-lg animate-in fade-in duration-500">
        <div className="text-center space-y-base">
          <div className="w-14 h-14 rounded-2xl bg-primary-fixed text-primary flex items-center justify-center mx-auto">
            <Icon name="shield" className="text-[28px]" fill />
          </div>
          <h2 className="font-headline text-headline-lg text-on-surface">Consentimiento informado</h2>
          <p className="text-body-md text-on-surface-variant">
            ActiveExam respeta tus derechos bajo la <strong>Ley 25.326</strong> y un DPIA aprobado. Leé con atención antes de continuar.
          </p>
          {texto && <p className="text-label-sm text-on-surface-variant">Versión {texto.version} · {texto.hash_texto}</p>}
        </div>

        <div className="grid sm:grid-cols-2 gap-md">
          {(texto?.bloques ?? []).map((b) => (
            <Card key={b.titulo} className="flex gap-sm">
              <div className="w-10 h-10 rounded-xl bg-primary-fixed text-primary flex items-center justify-center shrink-0">
                <Icon name={b.icono} />
              </div>
              <div>
                <h3 className="text-label-md font-semibold text-on-surface">{b.titulo}</h3>
                <p className="text-label-sm text-on-surface-variant mt-base leading-relaxed">{b.cuerpo}</p>
              </div>
            </Card>
          ))}
          {!texto && <p className="text-on-surface-variant">Cargando texto de consentimiento…</p>}
        </div>

        <Card className="bg-surface-container-low border-primary-fixed-dim/60">
          <label className="flex items-start gap-sm cursor-pointer">
            <input type="checkbox" checked={acepto} onChange={(e) => setAcepto(e.target.checked)}
              className="mt-base w-5 h-5 accent-[#4241bc] rounded" />
            <span className="text-body-md text-on-surface">
              Presto mi <strong>consentimiento libre, expreso e informado</strong> para el tratamiento de mis datos
              (incluido el <Term termKey="embedding">embedding biométrico</Term>, tratado como dato sensible) con la única finalidad de supervisar esta evaluación.
              Entiendo que <strong>el sistema nunca sanciona automáticamente</strong> y que toda decisión es humana.
            </span>
          </label>
        </Card>

        <div className="flex flex-col sm:flex-row items-center justify-between gap-md">
          <button onClick={alternativa} className="text-label-md text-on-surface-variant hover:text-primary inline-flex items-center gap-base">
            <Icon name="support_agent" className="text-[20px]" /> No acepto — solicitar vía alternativa
          </button>
          <Button onClick={aceptar} disabled={!acepto || guardando} icon={guardando ? undefined : 'check'} iconRight={guardando ? undefined : 'arrow_forward'}>
            {guardando ? <span className="inline-flex items-center gap-xs"><Icon name="progress_activity" className="ae-spin text-[20px]" /> Registrando…</span> : 'Acepto y continúo'}
          </Button>
        </div>
      </div>
    </StudentShell>
  );
}
