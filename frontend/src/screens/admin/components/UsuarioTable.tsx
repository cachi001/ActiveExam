import type { ReactNode } from 'react';
import { Icon, Avatar } from '../../../ui/components';
import { ActionMenu } from '../../../ui/ActionMenu';
import { RolBadge, EstadoSwitch } from './UsuarioHelpers';
import type { UsuarioAdmin } from '../../../lib/types';

interface UsuarioTableProps {
  usuarios: UsuarioAdmin[];
  fotos: Record<string, string>;
  cargando: boolean;
  total: number;
  esPropioUsuario: (u: UsuarioAdmin) => boolean;
  onVerDetalle: (u: UsuarioAdmin) => void;
  onEditar: (u: UsuarioAdmin) => void;
  onToggleEstado: (u: UsuarioAdmin) => void;
  /** Slot a la derecha del header (p. ej. el selector "Por página"). */
  headerRight?: ReactNode;
}

export function UsuarioTable({
  usuarios, fotos, cargando, total,
  esPropioUsuario, onVerDetalle, onEditar, onToggleEstado, headerRight,
}: UsuarioTableProps) {
  return (
    <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/60 shadow-card overflow-hidden">
      <div className="px-4 py-3 border-b border-outline-variant/40 flex items-center gap-2">
        <Icon name="group" className="text-[16px] text-on-surface-variant shrink-0" />
        <h2 className="text-[13px] font-semibold text-on-surface">
          Usuarios
          <span className="text-on-surface-variant font-normal ml-1">({total})</span>
        </h2>
        {headerRight && <div className="ml-auto">{headerRight}</div>}
      </div>

      {cargando ? (
        <div className="py-12 text-center text-on-surface-variant">
          <Icon name="progress_activity" className="ae-spin text-[28px] text-outline" />
        </div>
      ) : usuarios.length === 0 ? (
        <div className="py-12 text-center text-on-surface-variant space-y-base">
          <Icon name="group_off" className="text-[32px] text-outline" />
          <p className="text-[13px]">No se encontraron usuarios con esos filtros.</p>
        </div>
      ) : (
        <>
          {/* Tabla desktop */}
          <div className="hidden md:block overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-surface-container-low">
                  <th className="text-left text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-4 py-2.5">Nombre</th>
                  <th className="text-left text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-4 py-2.5">Email</th>
                  <th className="text-left text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-4 py-2.5">Legajo</th>
                  <th className="text-left text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-4 py-2.5">Roles</th>
                  <th className="text-left text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-4 py-2.5">Estado</th>
                  <th className="text-right text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-4 py-2.5">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/30">
                {usuarios.map((u) => (
                  <tr key={u.id} className="hover:bg-surface-container-low transition-colors group">
                    <td className="px-4 py-3.5 whitespace-nowrap">
                      <div className="flex items-center gap-3">
                        {fotos[u.id] ? (
                          <Avatar src={fotos[u.id]} alt={`Foto de ${u.nombre ?? u.email}`} size={34} />
                        ) : (
                          <div className="w-8 h-8 rounded-full bg-secondary-container text-on-secondary flex items-center justify-center font-semibold text-[13px] shrink-0">
                            {(u.nombre ?? u.email).charAt(0).toUpperCase()}
                          </div>
                        )}
                        <button
                          type="button"
                          onClick={() => onVerDetalle(u)}
                          className="text-[13px] font-semibold text-on-surface group-hover:text-primary transition-colors truncate max-w-[180px] text-left"
                        >
                          {u.nombre && u.apellido
                            ? `${u.nombre} ${u.apellido}`
                            : u.nombre ?? u.apellido ?? u.email}
                        </button>
                      </div>
                    </td>
                    <td className="px-4 py-3.5 whitespace-nowrap text-[13px] text-on-surface-variant truncate max-w-[220px]">
                      {u.email}
                    </td>
                    <td className="px-4 py-3.5 whitespace-nowrap">
                      <span className="font-mono text-[12px] text-on-surface-variant bg-surface-100 border border-outline-variant/40 px-2 py-0.5 rounded-md">
                        {u.id_institucional}
                      </span>
                    </td>
                    <td className="px-4 py-3.5 whitespace-nowrap">
                      <div className="flex flex-wrap gap-1">
                        {u.roles.map((r) => <RolBadge key={r} rol={r} />)}
                      </div>
                    </td>
                    <td className="px-4 py-3.5 whitespace-nowrap">
                      <EstadoSwitch usuario={u} esPropioUsuario={esPropioUsuario(u)} onToggle={onToggleEstado} />
                    </td>
                    <td className="px-4 py-3.5 whitespace-nowrap text-right">
                      <ActionMenu
                        ariaLabel={`Acciones de ${u.email}`}
                        items={[
                          { label: 'Ver detalle', icon: 'person_search', onClick: () => onVerDetalle(u) },
                          { label: 'Editar', icon: 'edit', onClick: () => onEditar(u) },
                        ]}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Cards mobile */}
          <div className="md:hidden divide-y divide-outline-variant/30">
            {usuarios.map((u) => (
              <div key={u.id} className="px-4 py-4 flex items-start gap-3">
                {fotos[u.id] ? (
                  <Avatar src={fotos[u.id]} alt={`Foto de ${u.nombre ?? u.email}`} size={40} />
                ) : (
                  <div className="w-10 h-10 rounded-full bg-secondary-container text-on-secondary flex items-center justify-center font-semibold text-[14px] shrink-0">
                    {(u.nombre ?? u.email).charAt(0).toUpperCase()}
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <button
                    type="button"
                    onClick={() => onVerDetalle(u)}
                    className="text-[13px] font-semibold text-on-surface hover:text-primary transition-colors truncate text-left w-full"
                  >
                    {u.nombre && u.apellido
                      ? `${u.nombre} ${u.apellido}`
                      : u.nombre ?? u.apellido ?? u.email}
                  </button>
                  <p className="text-[11px] text-on-surface-variant truncate mt-0.5">{u.email}</p>
                  <p className="text-[11px] font-mono text-on-surface-variant mt-0.5">{u.id_institucional}</p>
                  <div className="flex flex-wrap gap-1 mt-1.5">
                    {u.roles.map((r) => <RolBadge key={r} rol={r} />)}
                  </div>
                  <div className="mt-2">
                    <EstadoSwitch usuario={u} esPropioUsuario={esPropioUsuario(u)} onToggle={onToggleEstado} />
                  </div>
                </div>
                <ActionMenu
                  ariaLabel="Acciones del usuario"
                  items={[
                    { label: 'Ver detalle', icon: 'person_search', onClick: () => onVerDetalle(u) },
                    { label: 'Editar', icon: 'edit', onClick: () => onEditar(u) },
                  ]}
                />
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
