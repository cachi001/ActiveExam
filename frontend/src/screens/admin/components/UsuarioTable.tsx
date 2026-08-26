import type { ReactNode } from 'react';
import { Icon, Avatar } from '../../../ui/components';
import { AdminTable, type AdminColumn } from '../../../ui/AdminTable';
import { ActionMenu } from '../../../ui/ActionMenu';
import { RolBadge, EstadoSwitch } from './UsuarioHelpers';
import type { UsuarioAdmin } from '../../../lib/types';
import { usernameAdmin } from '../../../lib/identidadVisible';

interface UsuarioTableProps {
  usuarios: UsuarioAdmin[];
  fotos: Record<string, string>;
  cargando: boolean;
  total: number;
  esPropioUsuario: (u: UsuarioAdmin) => boolean;
  onVerDetalle: (u: UsuarioAdmin) => void;
  onEditar: (u: UsuarioAdmin) => void;
  onToggleEstado: (u: UsuarioAdmin) => void;
  headerRight?: ReactNode;
}

/** Items materia+comisión de un usuario (inscripciones si es estudiante,
 * comisiones a cargo si es tutor). Vacío para el resto de los roles. */
function itemsMateriaComision(usuario: UsuarioAdmin) {
  return [
    ...(usuario.inscripciones ?? []),
    ...(usuario.comisiones_a_cargo ?? []),
  ];
}

/** Guion chico y sutil — no el placeholder gigante que quedaba con el tamaño
 * de fuente por defecto de la tabla. */
function SinDato() {
  return <span className="text-surface-300 text-xs">—</span>;
}

/* c-78: acá el username técnico (`lti:1:7`) SÍ se muestra, a propósito. Es la
 * pantalla de administración de usuarios: el admin necesita ver la clave real
 * para identificar la cuenta, resolver un duplicado o cruzarla contra Moodle.
 * Lo que se corrigió es que el ALUMNO no la vea (su Perfil y el encabezado del
 * portal) — ver lib/identidadVisible.ts. */

/** Nombre legible de la fila: nombre+apellido, o el que haya, o el email.
 * Si TODO viene vacío (cuenta LTI provisionada antes del fix de 2026-08-19,
 * cuando Moodle no compartió nombre/email) la línea quedaba en blanco y solo
 * se veía el username técnico (`lti:7:1`) debajo — se explicita en vez de
 * dejarlo vacío. */
function nombreMostrar(u: { nombre?: string | null; apellido?: string | null; email?: string | null }): string {
  if (u.nombre && u.apellido) return `${u.nombre} ${u.apellido}`;
  if (u.nombre || u.apellido || u.email) return u.nombre ?? u.apellido ?? u.email ?? '';
  return 'Alumno sin datos de Moodle (vía LTI)';
}

/** Columna "Materia": código en negrita + nombre en gris debajo, con ícono —
 * mismo patrón que ExamList.tsx y el sistema de referencia (Active-IA). */
function MateriaCell({ usuario }: { usuario: UsuarioAdmin }) {
  const esEstudiante = usuario.roles.includes('estudiante');
  const esTutor = usuario.roles.includes('tutor');
  if (!esEstudiante && !esTutor) return <SinDato />;
  const items = itemsMateriaComision(usuario);
  if (items.length === 0) return <SinDato />;
  return (
    <div className="flex flex-col gap-1.5">
      {items.map((i) => (
        <div key={i.comision_id} className="flex items-center gap-2 min-w-0">
          <div className="w-7 h-7 rounded-md bg-primary-50 flex items-center justify-center shrink-0">
            <Icon name="folder_open" className="text-[14px] text-primary" />
          </div>
          <div className="min-w-0">
            <div className="text-sm font-medium text-surface-900 truncate">{i.materia_codigo}</div>
            <div className="text-xs text-surface-400 truncate">{i.materia_nombre}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

/** Columna "Comisión": mismo patrón código/nombre, sin ícono (ya lo trae la
 * columna Materia de la misma fila). */
function ComisionCell({ usuario }: { usuario: UsuarioAdmin }) {
  const esEstudiante = usuario.roles.includes('estudiante');
  const esTutor = usuario.roles.includes('tutor');
  if (!esEstudiante && !esTutor) return <SinDato />;
  const items = itemsMateriaComision(usuario);
  if (items.length === 0) return <SinDato />;
  return (
    <div className="flex flex-col gap-1.5">
      {items.map((i) => (
        <div key={i.comision_id} className="min-w-0">
          <div className="text-sm font-medium text-surface-900 truncate">{i.comision_codigo}</div>
          <div className="text-xs text-surface-400 truncate">{i.comision_nombre}</div>
        </div>
      ))}
    </div>
  );
}

function formatFecha(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    return new Intl.DateTimeFormat('es-AR', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export function UsuarioTable({
  usuarios, fotos, cargando, total,
  esPropioUsuario, onVerDetalle, onEditar, onToggleEstado, headerRight,
}: UsuarioTableProps) {
  const columns: AdminColumn<UsuarioAdmin>[] = [
    {
      key: 'usuario',
      header: 'Usuario',
      width: '20%',
      cell: (u) => (
        <div className="flex items-center gap-3">
          {fotos[u.id] ? (
            <Avatar src={fotos[u.id]} alt={`Foto de ${u.nombre ?? u.email}`} size={40} />
          ) : (
            <div className="w-10 h-10 rounded-full bg-primary text-on-primary flex items-center justify-center font-semibold text-sm shrink-0">
              {(u.nombre ?? u.email).charAt(0).toUpperCase()}
            </div>
          )}
          <div>
            <button
              type="button"
              onClick={() => onVerDetalle(u)}
              className="font-medium text-surface-900 hover:text-primary transition-colors text-left block"
            >
              {nombreMostrar(u)}
            </button>
            {/* c-78: nunca la clave interna `lti:1:7`. Se dice el ESTADO real. */}
            {(() => {
              const ident = usernameAdmin(u.username);
              return (
                <p
                  className={`text-xs mt-0.5 ${
                    ident.pendiente ? 'italic text-warning' : 'font-mono text-surface-400'
                  }`}
                >
                  {ident.texto}
                </p>
              );
            })()}
          </div>
        </div>
      ),
    },
    {
      key: 'email',
      header: 'Email',
      width: '15%',
      cell: (u) => (
        <div className="flex items-center gap-2 text-surface-600">
          <Icon name="mail" className="text-[16px] text-surface-400 shrink-0" />
          <span className="truncate">{u.email}</span>
        </div>
      ),
    },
    {
      key: 'roles',
      header: 'Roles',
      width: '11%',
      cell: (u) => (
        <div className="flex flex-wrap gap-1">
          {u.roles.map((r) => <RolBadge key={r} rol={r} />)}
        </div>
      ),
    },
    {
      key: 'materia',
      header: 'Materia',
      width: '13%',
      cell: (u) => <MateriaCell usuario={u} />,
    },
    {
      key: 'comision',
      header: 'Comisión',
      width: '11%',
      cell: (u) => <ComisionCell usuario={u} />,
    },
    {
      key: 'creado_en',
      header: 'Creación',
      width: '11%',
      cell: (u) => (
        <div className="flex items-center gap-1.5 text-surface-500 text-sm">
          <Icon name="calendar_today" className="text-[14px] text-surface-400 shrink-0" />
          {formatFecha(u.creado_en)}
        </div>
      ),
    },
    {
      key: 'ultimo_acceso',
      header: 'Último acceso',
      width: '10%',
      cell: (u) => (
        <div className="flex items-center gap-1.5 text-surface-500 text-sm">
          <Icon name="schedule" className="text-[14px] text-surface-400 shrink-0" />
          {u.ultimo_acceso_en
            ? formatFecha(u.ultimo_acceso_en)
            : <span className="italic text-surface-400">Nunca</span>}
        </div>
      ),
    },
    {
      key: 'estado',
      header: 'Estado',
      width: '10%',
      cell: (u) => (
        <EstadoSwitch usuario={u} esPropioUsuario={esPropioUsuario(u)} onToggle={onToggleEstado} />
      ),
    },
    {
      key: 'acciones',
      header: 'Acciones',
      width: '4%',
      align: 'right',
      headerAlign: 'right',
      cell: (u) => (
        <ActionMenu
          ariaLabel={`Acciones de ${u.email}`}
          items={[
            { label: 'Ver detalle', icon: 'person_search', onClick: () => onVerDetalle(u) },
            { label: 'Editar', icon: 'edit', onClick: () => onEditar(u) },
          ]}
        />
      ),
    },
  ];

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
      <div className="px-6 py-3 border-b border-gray-200 flex items-center gap-2">
        <Icon name="group" className="text-[16px] text-gray-400 shrink-0" />
        <h2 className="text-sm font-semibold text-gray-900">
          Usuarios
          <span className="text-gray-400 font-normal ml-1">({total})</span>
        </h2>
        {headerRight && <div className="ml-auto">{headerRight}</div>}
      </div>

      {/* Desktop */}
      <div className="hidden md:block">
        <AdminTable
          columns={columns}
          data={usuarios}
          keyExtractor={(u) => u.id}
          isLoading={cargando}
          emptyMessage="No se encontraron usuarios con esos filtros."
          tableMinWidth="1020px"
        />
      </div>

      {/* Mobile cards */}
      <div className="md:hidden divide-y divide-gray-200">
        {cargando && usuarios.length === 0 ? (
          <div className="py-12 text-center text-gray-400">
            <Icon name="progress_activity" className="ae-spin text-[28px]" />
          </div>
        ) : usuarios.length === 0 ? (
          <div className="py-12 text-center text-gray-500 space-y-2">
            <Icon name="group_off" className="text-[32px]" />
            <p className="text-sm">No se encontraron usuarios.</p>
          </div>
        ) : (
          usuarios.map((u) => (
            <div key={u.id} className="px-4 py-4 flex items-start gap-3">
              {fotos[u.id] ? (
                <Avatar src={fotos[u.id]} alt={`Foto de ${u.nombre ?? u.email}`} size={44} />
              ) : (
                <div className="w-11 h-11 rounded-full bg-primary text-on-primary flex items-center justify-center font-semibold text-sm shrink-0">
                  {(u.nombre ?? u.email).charAt(0).toUpperCase()}
                </div>
              )}
              <div className="flex-1 min-w-0">
                <button
                  type="button"
                  onClick={() => onVerDetalle(u)}
                  className="font-medium text-surface-900 hover:text-primary transition-colors truncate text-left w-full"
                >
                  {nombreMostrar(u)}
                </button>
                <p className="text-xs text-gray-500 truncate mt-0.5">{u.email}</p>
                {(() => {
                  const ident = usernameAdmin(u.username);
                  return (
                    <p
                      className={`text-xs mt-0.5 ${
                        ident.pendiente ? 'italic text-warning' : 'font-mono text-gray-400'
                      }`}
                    >
                      {ident.texto}
                    </p>
                  );
                })()}
                <div className="flex flex-wrap gap-1 mt-1.5">
                  {u.roles.map((r) => <RolBadge key={r} rol={r} />)}
                </div>
                {(u.roles.includes('estudiante') || u.roles.includes('tutor')) && (
                  <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1.5">
                    <MateriaCell usuario={u} />
                    <ComisionCell usuario={u} />
                  </div>
                )}
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
          ))
        )}
      </div>
    </div>
  );
}
