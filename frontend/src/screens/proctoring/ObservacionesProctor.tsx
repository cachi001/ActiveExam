/**
 * ObservacionesProctor — Panel de observaciones del proctor sobre una sesión (C-15 3.2).
 *
 * El proctor registra observaciones libres (múltiples, append-only) que son INSUMO
 * de la revisión humana de C-16. L2.5: una observación NO sanciona ni exime — es
 * contexto para la decisión HUMANA. Hace polling de `listarObservacionesProctor`.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Card, Button, Icon } from '../../ui/components';
import { api } from '../../lib/api';
import { useToast } from '../../ui/toast';
import type { ObservacionProctor } from '../../lib/types';

const POLL_MS = 6000;

function fechaCorta(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleString([], { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
}

export function ObservacionesProctor({
  sessionId,
  proctorActor,
}: {
  sessionId: string | null | undefined;
  proctorActor?: string | null;
}) {
  const toast = useToast();
  const [observaciones, setObservaciones] = useState<ObservacionProctor[]>([]);
  const [borrador, setBorrador] = useState('');
  const [guardando, setGuardando] = useState(false);
  const enVuelo = useRef(false);

  const refrescar = useCallback(async () => {
    if (!sessionId || enVuelo.current) return;
    enVuelo.current = true;
    try {
      setObservaciones(await api.listarObservacionesProctor(sessionId));
    } catch {
      // Degradación silenciosa: el próximo tick reintenta.
    } finally {
      enVuelo.current = false;
    }
  }, [sessionId]);

  useEffect(() => {
    setObservaciones([]);
    if (!sessionId) return;
    void refrescar();
    const id = setInterval(() => void refrescar(), POLL_MS);
    return () => clearInterval(id);
  }, [sessionId, refrescar]);

  const agregar = async () => {
    const texto = borrador.trim();
    if (!texto || !sessionId || guardando) return;
    setGuardando(true);
    try {
      const obs = await api.crearObservacionProctor(sessionId, texto, proctorActor);
      setObservaciones((prev) => [...prev, obs]);
      setBorrador('');
    } catch {
      toast.error('No se pudo guardar la observación');
    } finally {
      setGuardando(false);
    }
  };

  return (
    <Card className="space-y-sm">
      <h3 className="text-label-md font-bold text-on-surface border-b border-outline-variant/40 pb-base">
        Observaciones del proctor
        <span className="block text-[11px] font-normal text-on-surface-variant mt-px">
          Insumo para la revisión humana. No es un veredicto.
        </span>
      </h3>

      <div className="max-h-[260px] overflow-y-auto space-y-base">
        {observaciones.length === 0 ? (
          <p className="text-label-sm text-on-surface-variant italic text-center py-md">
            {sessionId ? 'Sin observaciones todavía.' : 'No hay sesión seleccionada.'}
          </p>
        ) : (
          observaciones.map((o) => (
            <div
              key={o.id}
              className="bg-surface-container-high rounded-xl px-sm py-base text-label-sm text-on-surface"
            >
              <p className="whitespace-pre-wrap">{o.texto}</p>
              <span className="block text-[10px] text-on-surface-variant mt-base">
                {o.proctor_actor ? `${o.proctor_actor} · ` : ''}
                {fechaCorta(o.creada_en)}
              </span>
            </div>
          ))
        )}
      </div>

      <div className="flex gap-base items-end">
        <textarea
          value={borrador}
          onChange={(e) => setBorrador(e.target.value)}
          disabled={!sessionId || guardando}
          rows={2}
          placeholder={sessionId ? 'Anotar una observación…' : 'No disponible'}
          className="flex-1 px-sm py-base text-label-md rounded-xl border border-outline-variant bg-surface-container-lowest focus:border-primary-container outline-none disabled:opacity-50 resize-none"
        />
        <Button onClick={() => void agregar()} disabled={!sessionId || guardando} className="h-auto px-md">
          <Icon name="add_comment" className="text-[18px]" />
        </Button>
      </div>
    </Card>
  );
}

export default ObservacionesProctor;
