import { Card, Button, Icon } from '../../../ui/components';
import type { ExamenContenidoResumen } from '../../../lib/types';
import type { GateImportado } from '../gateExamenImportado';

export type { GateImportado };

export interface ExamenImportadoCardProps {
  contenido: ExamenContenidoResumen;
  rindiendo: boolean;
  gate: GateImportado;
  perfilCompleto: boolean;
  onRendir: () => void;
  onCompletarPerfil: () => void;
}

export function ExamenImportadoCard({ contenido, rindiendo, gate, perfilCompleto, onRendir, onCompletarPerfil }: ExamenImportadoCardProps) {
  const bloqueado = !gate.habilitado;
  const tiempo = contenido.tiempo_limite_min;
  const faltaPerfil = !perfilCompleto;
  const inerte = faltaPerfil || bloqueado;
  // Intentos restantes (solo si el examen los limita). Se muestra cuando el alumno
  // TODAVÍA puede rendir, para que sepa cuántos le quedan antes de agotarlos.
  const restantes = gate.permitidos != null ? Math.max(0, gate.permitidos - gate.usados) : null;
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
          <p className="text-[12px] text-on-surface-variant mt-0.5">
            {contenido.cantidad_preguntas} {contenido.cantidad_preguntas === 1 ? 'pregunta' : 'preguntas'}
            {typeof tiempo === 'number' && tiempo > 0 && ` · ${tiempo} min`}
          </p>
          {faltaPerfil ? (
            <p className="text-[12px] text-warning mt-1 flex items-center gap-1">
              <Icon name="manage_accounts" className="text-[14px]" fill /> Completá tu perfil para poder rendir.
            </p>
          ) : bloqueado && gate.motivo ? (
            <p className="text-[12px] text-error mt-1 flex items-center gap-1">
              <Icon name="lock" className="text-[14px]" fill /> {gate.motivo}
            </p>
          ) : restantes != null && (
            <p className="text-[12px] text-on-surface-variant mt-1 flex items-center gap-1">
              <Icon name="replay" className="text-[14px]" /> Te queda{restantes === 1 ? '' : 'n'} {restantes} de {gate.permitidos} intento{gate.permitidos === 1 ? '' : 's'}.
            </p>
          )}
        </div>
      </div>
      {faltaPerfil ? (
        <Button variant="primary" size="sm" onClick={onCompletarPerfil} icon="manage_accounts">
          Completar perfil
        </Button>
      ) : bloqueado ? (
        // Si el alumno no puede rendir (intentos agotados / fuera de ventana) NO
        // mostramos un botón deshabilitado: el motivo (lock + texto) ya lo explica.
        null
      ) : (
        <Button
          variant="primary"
          size="sm"
          onClick={onRendir}
          disabled={rindiendo}
          icon={rindiendo ? undefined : 'play_arrow'}
        >
          {rindiendo ? 'Verificando…' : 'Rendir'}
        </Button>
      )}
    </Card>
  );
}
