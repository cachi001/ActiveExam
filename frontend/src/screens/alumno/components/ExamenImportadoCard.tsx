import { Card, Button, Icon } from '../../../ui/components';
import type { ExamenContenidoResumen } from '../../../lib/types';
import type { SesionEnCurso } from '../../../lib/apiProctoring/sesion';
import { textoVentana, type GateImportado } from '../gateExamenImportado';

export type { GateImportado };

export interface ExamenImportadoCardProps {
  contenido: ExamenContenidoResumen;
  rindiendo: boolean;
  gate: GateImportado;
  perfilCompleto: boolean;
  /**
   * La sesión que el alumno dejó abierta en ESTE examen, si la hay. Cambia la
   * tarjeta entera: deja de ofrecer "empezar" y pasa a ofrecer "continuar".
   */
  sesionEnCurso?: SesionEnCurso | null;
  onRendir: () => void;
  onCompletarPerfil: () => void;
}

export function ExamenImportadoCard({ contenido, rindiendo, gate, perfilCompleto, sesionEnCurso, onRendir, onCompletarPerfil }: ExamenImportadoCardProps) {
  const bloqueado = !gate.habilitado;
  // Examen empezado y sin entregar. El backend reanuda la MISMA sesión (mismo
  // cronómetro, respuestas restauradas) y el conteo de intentos solo mira las
  // finalizadas, así que continuar no consume nada.
  const enCurso = !!sesionEnCurso && !bloqueado;
  const tiempo = contenido.tiempo_limite_min;
  const faltaPerfil = !perfilCompleto;
  const inerte = faltaPerfil || bloqueado;
  // Intentos restantes (solo si el examen los limita). Se muestra cuando el alumno
  // TODAVÍA puede rendir, para que sepa cuántos le quedan antes de agotarlos.
  const restantes = gate.permitidos != null ? Math.max(0, gate.permitidos - gate.usados) : null;
  // "Sin fecha de cierre" en vez de callar: que no haya fecha es información que
  // el alumno necesita — si no la ve, la supone. Igual con el tiempo. En los
  // exámenes sin ninguna de las dos, la tarjeta se quedaba con una sola línea.
  const ventana = textoVentana(contenido.apertura, contenido.cierre) ?? 'Sin fecha de cierre';
  const tiempoTexto =
    typeof tiempo === 'number' && tiempo > 0 ? `${tiempo} min` : 'Sin límite de tiempo';
  const contexto = [contenido.materia_nombre, contenido.comision_nombre]
    .filter(Boolean)
    .join(' · ');
  return (
    <Card className="flex items-center justify-between gap-md p-md">
      <div className="flex items-start gap-sm min-w-0">
        <div className={`w-9 h-9 rounded-md flex items-center justify-center shrink-0 mt-0.5 ${inerte ? 'bg-surface-container text-on-surface-variant' : 'bg-primary-fixed text-primary'}`}>
          <Icon name="assignment" className="text-[18px]" />
        </div>
        <div className="min-w-0">
          <p className="text-[14px] font-medium text-on-surface leading-tight truncate">
            {contenido.titulo}
          </p>
          {/* Materia y comisión: la API ya las mandaba y no se estaban usando.
              Un alumno con varias materias necesita saber de cuál es este examen. */}
          {contexto && (
            <p className="text-[12px] text-on-surface-variant mt-0.5 truncate">{contexto}</p>
          )}
          {/* La cantidad de preguntas NO se le muestra al alumno (decisión del
              dueño, 28/8/2026). El tiempo y la ventana sí: los necesita para
              organizarse, y el motivo del gate solo nombra la fecha cuando
              bloquea. */}
          <p className="text-[12px] text-on-surface-variant mt-0.5 flex items-center gap-1">
            <Icon name="schedule" className="text-[14px]" /> {tiempoTexto}
            <span className="text-on-surface-variant/50">·</span>
            <Icon name="event" className="text-[14px]" /> {ventana}
          </p>
          {/* El motivo del BLOQUEO gana sobre el del perfil: un examen cerrado
              decía "Completá tu perfil", el alumno hacía todo el enrollment y
              recién ahí descubría que ese examen no se podía rendir. Completar
              el perfil no lo vuelve rendible. */}
          {bloqueado && gate.motivo ? (
            <p className="text-[12px] text-error mt-1 flex items-center gap-1">
              <Icon name="lock" className="text-[14px]" fill /> {gate.motivo}
            </p>
          ) : enCurso ? (
            /* Gana sobre el cartel de intentos, que es justo el que asustaba: el
               alumno al que se le cortó la conexión leía "Tenés un solo intento"
               y entendía que lo había gastado. Acá hay que decirle lo contrario,
               que su examen sigue donde lo dejó. */
            <p className="text-[12px] text-warning mt-1 flex items-center gap-1">
              <Icon name="play_circle" className="text-[14px]" fill />
              Lo tenés empezado. Seguís donde lo dejaste, sin gastar otro intento.
            </p>
          ) : faltaPerfil ? (
            <p className="text-[12px] text-warning mt-1 flex items-center gap-1">
              <Icon name="manage_accounts" className="text-[14px]" fill /> Completá tu perfil para poder rendir.
            </p>
          ) : gate.permitidos === 1 ? (
            // "Te queda 1 de 1 intento" no dice nada: en un examen de un solo
            // intento no hay nada que quede. Lo que el alumno necesita saber es
            // que no va a poder repetirlo.
            <p className="text-[12px] text-on-surface-variant mt-1 flex items-center gap-1">
              <Icon name="looks_one" className="text-[14px]" /> Tenés un solo intento.
            </p>
          ) : restantes != null && (
            <p className="text-[12px] text-on-surface-variant mt-1 flex items-center gap-1">
              <Icon name="replay" className="text-[14px]" /> Te queda{restantes === 1 ? '' : 'n'} {restantes} de {gate.permitidos} intentos.
            </p>
          )}
        </div>
      </div>
      {/* Mismo orden que el mensaje: si está bloqueado no se ofrece "Completar
          perfil", que ahí sería trabajo inútil. */}
      {bloqueado ? (
        // Si el alumno no puede rendir (fuera de ventana / intentos agotados /
        // examen sin preguntas) NO mostramos un botón deshabilitado: el motivo
        // de arriba ya lo explica.
        null
      ) : faltaPerfil ? (
        <Button variant="primary" size="sm" onClick={onCompletarPerfil} icon="manage_accounts">
          Completar perfil
        </Button>
      ) : (
        // El botón lleva a la ficha del examen (`/pre-examen`), donde está el
        // "Comenzar examen" que sí arranca la rendición. Decía "Rendir" y
        // prometía algo que esa pantalla todavía no hace.
        <Button
          variant="primary"
          size="sm"
          onClick={onRendir}
          disabled={rindiendo}
          icon={rindiendo ? undefined : enCurso ? 'play_arrow' : 'arrow_forward'}
        >
          {rindiendo ? 'Verificando…' : enCurso ? 'Continuar examen' : 'Ver examen'}
        </Button>
      )}
    </Card>
  );
}
