/**
 * ChatBox — Canal de chat bidireccional proctor↔alumno (C-15).
 *
 * Reutilizable por ambos lados: el `yo` indica quién soy ('alumno' | 'proctor'),
 * para alinear y colorear mis mensajes a la derecha y los del otro a la izquierda.
 *
 * Hace polling incremental de `listarMensajesChat(sessionId, ultimoTs)` cada
 * POLL_MS para traer los mensajes nuevos del otro extremo, y envía con
 * `enviarMensajeChat(sessionId, yo, texto)`. Si no hay sessionId todavía, el
 * canal se muestra deshabilitado (la sesión aún no arrancó).
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Card, Button, Icon } from './components';
import { api } from '../lib/api';
import { useToast } from './toast';
import type { AutorChat, MensajeChat } from '../lib/types';

/** Intervalo de polling del chat (ms). Suficiente para sentirse "en vivo". */
const POLL_MS = 3500;

const AUTOR_LABEL: Record<AutorChat, string> = {
  alumno: 'Estudiante',
  proctor: 'Proctor',
};

function horaCorta(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export function ChatBox({
  sessionId,
  yo,
  titulo = 'Canal con el proctor',
  altura = 'h-[160px]',
  readOnly = false,
}: {
  sessionId: string | null | undefined;
  yo: AutorChat;
  titulo?: string;
  altura?: string;
  /** Solo lectura (sesión grabada): muestra el historial sin caja de envío. */
  readOnly?: boolean;
}) {
  const toast = useToast();
  const [mensajes, setMensajes] = useState<MensajeChat[]>([]);
  const [borrador, setBorrador] = useState('');
  const [enviando, setEnviando] = useState(false);

  // Último timestamp recibido → polling incremental (solo trae los nuevos).
  const ultimoTs = useRef<string | undefined>(undefined);
  // Evita refrescos solapados y stale closures (igual patrón que Proctor.tsx).
  const enVuelo = useRef(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const merge = useCallback((nuevos: MensajeChat[]) => {
    if (nuevos.length === 0) return;
    setMensajes((prev) => {
      const vistos = new Set(prev.map((m) => m.id));
      const add = nuevos.filter((m) => !vistos.has(m.id));
      if (add.length === 0) return prev;
      return [...prev, ...add];
    });
    const last = nuevos[nuevos.length - 1];
    if (!ultimoTs.current || last.creado_en > ultimoTs.current) {
      ultimoTs.current = last.creado_en;
    }
  }, []);

  const refrescar = useCallback(async () => {
    if (!sessionId || enVuelo.current) return;
    enVuelo.current = true;
    try {
      const data = await api.listarMensajesChat(sessionId, ultimoTs.current);
      merge(data);
    } catch {
      // Degradación silenciosa: el próximo tick reintenta solo.
    } finally {
      enVuelo.current = false;
    }
  }, [sessionId, merge]);

  // Polling con cleanup: carga inicial + intervalo único que se limpia al unmount.
  // Al cambiar de sesión, reseteamos el cursor y la lista para no mezclar canales.
  useEffect(() => {
    ultimoTs.current = undefined;
    setMensajes([]);
    if (!sessionId) return;
    void refrescar();
    // Solo lectura (grabada): carga única, sin polling.
    if (readOnly) return;
    const id = setInterval(() => void refrescar(), POLL_MS);
    return () => clearInterval(id);
  }, [sessionId, refrescar, readOnly]);

  // Autoscroll al fondo cuando llega/envío un mensaje.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [mensajes]);

  const enviar = async () => {
    const texto = borrador.trim();
    if (!texto || !sessionId || enviando) return;
    setEnviando(true);
    try {
      const msg = await api.enviarMensajeChat(sessionId, yo, texto);
      merge([msg]);
      setBorrador('');
    } catch {
      toast.error('No se pudo enviar el mensaje');
    } finally {
      setEnviando(false);
    }
  };

  return (
    <Card className="space-y-sm">
      <h3 className="text-label-md font-bold text-on-surface border-b border-outline-variant/40 pb-base">
        {titulo}
      </h3>

      <div
        ref={scrollRef}
        className={`${altura} overflow-y-auto space-y-base bg-white border border-outline-variant/40 rounded-xl p-sm`}
      >
        {mensajes.length === 0 ? (
          <p className="text-label-sm text-on-surface-variant italic text-center py-md">
            {!sessionId
              ? 'El canal se habilita al iniciar la sesión.'
              : readOnly
                ? 'No hubo mensajes en esta sesión.'
                : 'Sin mensajes todavía.'}
          </p>
        ) : (
          mensajes.map((m) => {
            const mio = m.autor === yo;
            return (
              <div key={m.id} className={`flex flex-col ${mio ? 'items-end' : 'items-start'}`}>
                <div
                  className={`max-w-[85%] px-sm py-base rounded-xl text-label-sm ${
                    mio
                      ? 'bg-primary-fixed/60 text-on-surface'
                      : 'bg-surface-container-high text-on-surface'
                  }`}
                >
                  {m.texto}
                </div>
                <span className="text-[10px] text-on-surface-variant mt-px px-base">
                  {AUTOR_LABEL[m.autor]} · {horaCorta(m.creado_en)}
                </span>
              </div>
            );
          })
        )}
      </div>

      {!readOnly && (
        <div className="flex gap-base">
          <input
            value={borrador}
            onChange={(e) => setBorrador(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && void enviar()}
            disabled={!sessionId || enviando}
            placeholder={sessionId ? 'Escribir mensaje…' : 'Canal no disponible'}
            className="flex-1 h-10 px-sm py-base text-label-md rounded-xl border border-outline-variant bg-surface-container-lowest focus:border-primary-container outline-none disabled:opacity-50"
          />
          <Button
            onClick={() => void enviar()}
            disabled={!sessionId || enviando}
            aria-label="Enviar mensaje"
            className="shrink-0 h-10 w-10 !p-0"
          >
            <Icon name="send" className="text-[18px]" />
          </Button>
        </div>
      )}
    </Card>
  );
}

export default ChatBox;
