import { Icon } from '../../ui/components';

export type SyncResult = {
  enviadas: number;
  fallidas: number;
  sin_token: number;
  total: number;
  mensaje?: string;
};

export function SyncResultBanner({ result, onClose }: { result: SyncResult; onClose: () => void }) {
  const todoSinToken = result.sin_token > 0 && result.enviadas === 0 && result.fallidas === 0;
  const tieneFallidas = result.fallidas > 0;
  const tone = todoSinToken ? 'warning' : tieneFallidas ? 'error' : 'success';

  const bgMap = { warning: 'bg-warning-container', error: 'bg-error-container', success: 'bg-success-container' };
  const textMap = { warning: 'text-warning', error: 'text-on-error-container', success: 'text-success' };
  const iconMap = { warning: 'info', error: 'error', success: 'check_circle' };

  return (
    <div className={`flex items-start gap-sm p-md rounded-xl ${bgMap[tone]} mb-md`}>
      <Icon name={iconMap[tone]} className={`${textMap[tone]} text-[20px] shrink-0 mt-0.5`} fill />
      <div className="flex-1 min-w-0">
        {todoSinToken ? (
          <p className={`text-label-md font-semibold ${textMap[tone]}`}>
            Token de Moodle no configurado
          </p>
        ) : (
          <p className={`text-label-md font-semibold ${textMap[tone]}`}>
            Sincronización completada
          </p>
        )}
        <ul className="mt-xs space-y-base text-label-sm text-on-surface">
          {result.enviadas > 0 && <li>✓ {result.enviadas} nota{result.enviadas !== 1 ? 's' : ''} enviada{result.enviadas !== 1 ? 's' : ''} a Moodle</li>}
          {result.fallidas > 0 && <li>✗ {result.fallidas} fallida{result.fallidas !== 1 ? 's' : ''}</li>}
          {result.sin_token > 0 && (
            <li>
              {result.sin_token} sin token
              {todoSinToken && ' — Configurá el token de Moodle en Configuración del sistema para habilitar la sincronización.'}
            </li>
          )}
        </ul>
        {result.mensaje && !todoSinToken && (
          <p className="mt-xs text-label-sm text-on-surface-variant">{result.mensaje}</p>
        )}
      </div>
      <button type="button" onClick={onClose} aria-label="Cerrar" className="text-on-surface-variant hover:text-on-surface shrink-0">
        <Icon name="close" className="text-[18px]" />
      </button>
    </div>
  );
}
