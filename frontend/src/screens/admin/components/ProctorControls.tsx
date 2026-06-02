import { Button, Card, SectionTitle, RangeInput } from '../../../ui/components';
import { DESAFIOS } from '../../../lib/api';
import type { SesionEnVivo } from '../../../lib/types';

interface ProctorControlsProps {
  umbral: number;
  onUmbralChange: (v: number) => void;
  retos: string[];
  onRetosChange: (ids: string[]) => void;
  lista: SesionEnVivo[];
  mensaje: string;
  onMensajeChange: (v: string) => void;
  destinatario: string;
  onDestinatarioChange: (v: string) => void;
  onEnviar: () => void;
}

export function ProctorControls({
  umbral,
  onUmbralChange,
  retos,
  onRetosChange,
  lista,
  mensaje,
  onMensajeChange,
  destinatario,
  onDestinatarioChange,
  onEnviar,
}: ProctorControlsProps) {
  return (
    <div className="space-y-lg">
      <Card className="space-y-md">
        <SectionTitle>Controles de proctoring</SectionTitle>
        <RangeInput
          label="Umbral de cola de revisión"
          value={umbral}
          min={30}
          max={90}
          unit="%"
          hint="Si un estudiante supera este score al terminar, entra automáticamente a revisión humana."
          onChange={onUmbralChange}
        />
        <div className="space-y-base">
          <label className="text-label-sm uppercase tracking-wide text-on-surface-variant font-semibold">Retos activos pre-examen</label>
          <div className="grid grid-cols-2 gap-base">
            {DESAFIOS.slice(0, 4).map((d) => {
              const on = retos.includes(d.id);
              return (
                <label key={d.id} className="flex items-center gap-base p-base rounded-lg bg-surface-container-low border border-outline-variant/40 cursor-pointer text-label-sm">
                  <input
                    type="checkbox"
                    checked={on}
                    className="accent-primary"
                    onChange={(e) => onRetosChange(e.target.checked ? [...retos, d.id] : retos.filter((x) => x !== d.id))}
                  />
                  <span className="font-semibold">{d.label}</span>
                </label>
              );
            })}
          </div>
        </div>
      </Card>

      <Card className="space-y-sm">
        <SectionTitle>Mensaje correctivo</SectionTitle>
        <select
          value={destinatario}
          onChange={(e) => onDestinatarioChange(e.target.value)}
          className="w-full text-label-md bg-surface-container-low border border-outline-variant rounded-xl px-sm py-base font-semibold outline-none"
        >
          {lista.map((s) => <option key={s.id} value={s.estudiante}>{s.estudiante} (Riesgo {s.score}%)</option>)}
        </select>
        <textarea
          rows={3}
          value={mensaje}
          onChange={(e) => onMensajeChange(e.target.value)}
          placeholder="Escribí un mensaje para el estudiante…"
          className="w-full text-label-md bg-surface-container-low border border-outline-variant rounded-xl px-sm py-base outline-none focus:border-primary-container"
        />
        <Button variant="secondary" icon="shield" onClick={onEnviar} className="w-full">Enviar advertencia cifrada</Button>
      </Card>
    </div>
  );
}
