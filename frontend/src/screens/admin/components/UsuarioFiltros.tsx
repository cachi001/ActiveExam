import { Icon, Card, SectionTitle } from '../../../ui/components';
import { OPCIONES_ROL, OPCIONES_ESTADO } from './UsuarioHelpers';

interface UsuarioFiltrosProps {
  filtroRol: string;
  filtroEstado: string;
  qInput: string;
  onFiltroRol: (v: string) => void;
  onFiltroEstado: (v: string) => void;
  onQChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onQKeyDown: (e: React.KeyboardEvent<HTMLInputElement>) => void;
}

export function UsuarioFiltros({
  filtroRol, filtroEstado, qInput,
  onFiltroRol, onFiltroEstado, onQChange, onQKeyDown,
}: UsuarioFiltrosProps) {
  return (
    <Card>
      <SectionTitle sub="Filtrá por rol, estado o búsqueda de texto.">Filtros</SectionTitle>
      <div className="flex flex-col sm:flex-row gap-md mt-md flex-wrap">
        <div className="flex flex-col gap-xs min-w-[160px]">
          <label className="text-[11px] font-semibold text-on-surface-variant uppercase tracking-wide">Rol</label>
          <select
            value={filtroRol}
            onChange={(e) => onFiltroRol(e.target.value)}
            className="text-[13px] rounded-lg border border-outline-variant/60 bg-surface-container-low px-3 py-1.5 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/30 text-on-surface"
          >
            {OPCIONES_ROL.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-xs min-w-[140px]">
          <label className="text-[11px] font-semibold text-on-surface-variant uppercase tracking-wide">Estado</label>
          <select
            value={filtroEstado}
            onChange={(e) => onFiltroEstado(e.target.value)}
            className="text-[13px] rounded-lg border border-outline-variant/60 bg-surface-container-low px-3 py-1.5 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/30 text-on-surface"
          >
            {OPCIONES_ESTADO.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-xs flex-1 min-w-[200px]">
          <label className="text-[11px] font-semibold text-on-surface-variant uppercase tracking-wide">Buscar</label>
          <div className="relative">
            <Icon name="search" className="text-[16px] text-on-surface-variant absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="search"
              placeholder="Nombre, email o legajo… (Enter)"
              value={qInput}
              onChange={onQChange}
              onKeyDown={onQKeyDown}
              className="w-full pl-8 pr-3 py-1.5 text-[13px] rounded-lg border border-outline-variant/60 bg-surface-container-low focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/30 placeholder:text-on-surface-variant/60"
            />
          </div>
        </div>
      </div>
    </Card>
  );
}
