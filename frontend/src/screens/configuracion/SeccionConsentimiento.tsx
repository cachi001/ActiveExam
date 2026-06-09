/**
 * SeccionConsentimiento — edición del texto que los alumnos confirman.
 *
 * Carga los bloques del consentimiento (api.getConsentText) y permite editar
 * título y cuerpo de cada uno. En demo el guardado es local (toast); con backend
 * real iría a un PUT /consent/text que versione el texto.
 */
import { useState, useEffect } from 'react';
import { Card, Button, Icon } from '../../ui/components';
import { useToast } from '../../ui/toast';
import { api } from '../../lib/api';
import type { BloqueConsentimiento } from '../../lib/types';

export default function SeccionConsentimiento() {
  const toast = useToast();
  const [bloques, setBloques] = useState<BloqueConsentimiento[]>([]);
  const [version, setVersion] = useState('');
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    api.getConsentText()
      .then((t) => { setBloques(t.bloques); setVersion(t.version); })
      .catch((e) => toast.error(`No se pudo cargar el consentimiento: ${e instanceof Error ? e.message : String(e)}`))
      .finally(() => setCargando(false));
  }, [toast]);

  function setBloque(i: number, field: keyof BloqueConsentimiento, value: string) {
    setBloques((prev) => prev.map((b, idx) => (idx === i ? { ...b, [field]: value } : b)));
  }

  async function guardar() {
    setGuardando(true);
    await new Promise((r) => setTimeout(r, 400));
    setGuardando(false);
    toast.success('Texto de consentimiento guardado');
  }

  if (cargando) {
    return (
      <div className="space-y-lg max-w-3xl">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-[140px] rounded-2xl border border-outline-variant/40 bg-white animate-pulse" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-lg max-w-3xl">
      <div className="flex items-center gap-base text-[13px] text-on-surface-variant">
        <Icon name="article" className="text-[18px] text-primary" />
        <span>Versión <span className="font-mono font-semibold text-on-surface">{version}</span> — editá el texto que los alumnos leen y confirman antes de rendir.</span>
      </div>

      {bloques.map((b, i) => (
        <Card key={i} className="space-y-sm">
          <input
            type="text"
            value={b.titulo}
            onChange={(e) => setBloque(i, 'titulo', e.target.value)}
            className="w-full text-title-md font-headline text-on-surface bg-transparent border-b border-transparent hover:border-outline-variant focus:border-primary focus:outline-none pb-1 transition-colors"
            aria-label={`Título del bloque ${i + 1}`}
          />
          <textarea
            value={b.cuerpo}
            onChange={(e) => setBloque(i, 'cuerpo', e.target.value)}
            rows={3}
            className="w-full text-[13px] text-on-surface-variant bg-white rounded-xl border border-outline-variant p-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors resize-y"
            aria-label={`Cuerpo del bloque ${i + 1}`}
          />
        </Card>
      ))}

      <div className="flex justify-end">
        <Button icon="save" onClick={guardar} disabled={guardando}>
          {guardando ? 'Guardando…' : 'Guardar consentimiento'}
        </Button>
      </div>
    </div>
  );
}
