/**
 * ChatBox — Canal de chat bidireccional tutor↔alumno (C-15; actor renombrado
 * de 'proctor' a 'tutor' en c-76 bloque 6, D4).
 *
 * Reutilizable por ambos lados: el `yo` indica quién soy ('alumno' | 'tutor'),
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
import { AVISO_SOLO_RESPONDER, puedeResponder } from './chat/soloResponder';
import { intervaloDeChat } from './chat/chatCadencia';
import type { AutorChat, MensajeChat } from '../lib/types';

/**
 * Cooldown anti-flood entre mensajes del ALUMNO (segundos). No bloquea la
 * comunicación (puede mandar varios sin esperar respuesta del tutor), solo
 * evita el envío en ráfaga. El tutor responde sin cooldown.
 */
const COOLDOWN_ALUMNO_S = 5;

const AUTOR_LABEL: Record<AutorChat, string> = {
  alumno: 'Estudiante',
  tutor: 'Tutor',
};

function horaCorta(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export function ChatBox({
  sessionId,
  yo,
  titulo = 'Canal con el tutor',
  altura = 'h-[160px]',
  readOnly = false,
  soloResponder = false,
}: {
  sessionId: string | null | undefined;
  yo: AutorChat;
  titulo?: string;
  altura?: string;
  /** Solo lectura (sesión grabada): muestra el historial sin caja de envío. */
  readOnly?: boolean;
  /**
   * El alumno RESPONDE, no inicia (decisión del dueño, 29/8/2026). Con esto en
   * `true` la caja queda bloqueada hasta que el tutor escriba: el canal es para
   * que quien supervisa pregunte algo puntual, no una vía de consulta durante la
   * evaluación.
   */
  soloResponder?: boolean;
}) {
  const toast = useToast();
  const [mensajes, setMensajes] = useState<MensajeChat[]>([]);
  // El alumno no inicia la conversación: se habilita cuando el tutor escribe.
  const bloqueadoHastaQueEscriba = soloResponder && !puedeResponder(mensajes);
  const [borrador, setBorrador] = useState('');
  const [enviando, setEnviando] = useState(false);
  // Cooldown anti-flood (solo alumno): segundos restantes hasta poder reenviar.
  const aplicaCooldown = yo === 'alumno';
  const [cooldown, setCooldown] = useState(0);

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

  // Cadencia adaptativa: mientras nadie escribió se pregunta espaciado, y en cuanto
  // hay conversación se vuelve a 3,5 s. Con 100 alumnos el intervalo fijo se
  // llevaba ~29 de los 80 req/s del techo y frenaba el autoguardado del examen.
  // Ver `chat/chatCadencia.ts`.
  const intervaloMs = intervaloDeChat(mensajes[mensajes.length - 1]?.creado_en);

  // Dos efectos separados a propósito. El reseteo depende SOLO de la sesión: si
  // viviera junto al intervalo, pasar de la cadencia lenta a la rápida (o sea, la
  // llegada del primer mensaje) volvería a vaciar la lista y el mensaje recién
  // llegado desaparecería de pantalla justo cuando aparece.
  useEffect(() => {
    ultimoTs.current = undefined;
    setMensajes([]);
    if (sessionId) void refrescar();
  }, [sessionId, refrescar]);

  // Polling con cleanup. Solo lectura (grabada): carga única, sin polling.
  useEffect(() => {
    if (!sessionId || readOnly) return;
    const id = setInterval(() => void refrescar(), intervaloMs);
    return () => clearInterval(id);
  }, [sessionId, refrescar, readOnly, intervaloMs]);

  // Autoscroll al fondo cuando llega/envío un mensaje.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [mensajes]);

  const enviar = async () => {
    const texto = borrador.trim();
    if (!texto || !sessionId || enviando || cooldown > 0) return;
    setEnviando(true);
    try {
      const msg = await api.enviarMensajeChat(sessionId, yo, texto);
      merge([msg]);
      setBorrador('');
      if (aplicaCooldown) {
        setCooldown(COOLDOWN_ALUMNO_S);
      }
    } catch {
      toast.error('No se pudo enviar el mensaje');
    } finally {
      setEnviando(false);
    }
  };

  // Tick del cooldown (1/s). Al llegar a 0 se limpia el aviso de "enviado".
  useEffect(() => {
    if (cooldown <= 0) return;
    const t = setInterval(() => setCooldown((c) => Math.max(0, c - 1)), 1000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cooldown > 0]);

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
        <>
          <div className="flex gap-base">
            <input
              value={borrador}
              onChange={(e) => setBorrador(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && void enviar()}
              disabled={!sessionId || enviando || cooldown > 0 || bloqueadoHastaQueEscriba}
              placeholder={
                bloqueadoHastaQueEscriba
                  ? 'Esperá a que el tutor te escriba'
                  : sessionId
                    ? 'Escribir mensaje…'
                    : 'Canal no disponible'
              }
              className="flex-1 h-10 px-sm py-base text-label-md rounded-xl border border-outline-variant bg-surface-container-lowest focus:border-primary-container outline-none disabled:opacity-50"
            />
            <Button
              onClick={() => void enviar()}
              disabled={!sessionId || enviando || cooldown > 0 || bloqueadoHastaQueEscriba}
              aria-label="Enviar mensaje"
              className="shrink-0 h-10 w-10 !p-0"
            >
              <Icon name="send" className="text-[18px]" />
            </Button>
          </div>
          {bloqueadoHastaQueEscriba && (
            <p className="text-[11px] text-on-surface-variant flex items-start gap-1">
              <Icon name="lock" className="text-[13px] shrink-0 mt-px" fill />
              {AVISO_SOLO_RESPONDER}
            </p>
          )}
          {aplicaCooldown && cooldown > 0 && (
            <p className="text-[11px] text-on-surface-variant flex items-center gap-1">
              <Icon name="check_circle" className="text-[13px] text-success" fill />
              Mensaje enviado — el tutor lo verá. Podés escribir de nuevo en {cooldown}s.
            </p>
          )}
        </>
      )}
    </Card>
  );
}

export default ChatBox;
