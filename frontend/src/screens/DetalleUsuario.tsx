/**
 * DetalleUsuario — página de detalle de un usuario del sistema (C-68).
 *
 * Ruta: /admin/usuarios/:id  (id leído desde sessionStorage via useRouteParam)
 * Secciones:
 *   1. Datos personales (roles con badges de color, proveedor de auth, estado)
 *   2. Consentimiento de perfil (semántica de color: verde/rojo/neutro)
 *   3. Captura de referencia biométrica (foto + metadatos; sin embedding crudo)
 *
 * Standard de diseño: igual a Configuracion.tsx (Card + SectionTitle, tokens propios).
 * Manejo de carga con skeletons; si un endpoint falla la sección muestra aviso
 * sin romper el resto (aislamiento de error por sección).
 */

import { useEffect, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Card, SectionTitle, Badge, Button, Icon } from '../ui/components';
import { STAFF_NAV } from '../ui/nav';
import { useNavigate, useRouteParam } from '../lib/router';
import { api } from '../lib/api';
import type { UsuarioAdmin } from '../lib/types';
import { getRolLabel } from '../lib/constants/roles';

// ---------------------------------------------------------------------------
// Tipos locales de sección
// ---------------------------------------------------------------------------

type ConsentData = {
  estado: 'otorgado' | 'revocado' | null;
  version_texto: string | null;
  hash_texto: string | null;
  timestamp: string | null;
};

type BiometriaData = {
  tiene_referencia_vigente: boolean;
  algoritmo: string | null;
  fecha_expiracion: string | null;
  created_at: string | null;
  tiene_foto: boolean;
  foto_hash: string | null;
  foto_created_at: string | null;
};

type SectionState<T> =
  | { status: 'loading' }
  | { status: 'ok'; data: T }
  | { status: 'error'; message: string };

// ---------------------------------------------------------------------------
// Helpers de presentación
// ---------------------------------------------------------------------------

function formatFecha(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    return new Intl.DateTimeFormat('es-AR', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

/** Badge de rol con color semántico. */
function RolBadge({ rol }: { rol: string }) {
  const toneMap: Record<string, 'primary' | 'success' | 'warning' | 'error' | 'neutral'> = {
    admin_sistema: 'primary',
    proctor: 'warning',
    estudiante: 'success',
  };
  const tone = toneMap[rol] ?? 'neutral';
  return <Badge tone={tone}>{getRolLabel(rol)}</Badge>;
}

/** Skeleton para una sección mientras carga. */
function SectionSkeleton() {
  return (
    <div className="space-y-3 animate-pulse">
      {[1, 2, 3].map((i) => (
        <div key={i} className="h-5 bg-surface-container-high rounded-lg w-3/4" />
      ))}
    </div>
  );
}

/** Aviso de error de sección. */
function SectionError({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-2 text-error text-[13px] bg-error-container/40 rounded-lg px-3 py-2.5">
      <Icon name="error" className="text-[18px] shrink-0" fill />
      <span>{message}</span>
    </div>
  );
}

/** Fila de dato. */
function DataRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-baseline gap-1 sm:gap-3 py-2 border-b border-outline-variant/30 last:border-0">
      <span className="text-[11px] font-semibold uppercase tracking-wide text-on-surface-variant w-48 shrink-0">
        {label}
      </span>
      <span className="text-[13px] text-on-surface flex-1">{value ?? '—'}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Componente principal
// ---------------------------------------------------------------------------

export default function DetalleUsuario() {
  const navigate = useNavigate();
  const usuarioId = useRouteParam('id');

  const [usuario, setUsuario] = useState<SectionState<UsuarioAdmin & { eliminado_en?: string | null }>>({ status: 'loading' });
  const [consent, setConsent] = useState<SectionState<ConsentData>>({ status: 'loading' });
  const [biometria, setBiometria] = useState<SectionState<BiometriaData>>({ status: 'loading' });
  const [foto, setFoto] = useState<string | null>(null);

  useEffect(() => {
    if (!usuarioId) {
      setUsuario({ status: 'error', message: 'No se encontró el ID del usuario.' });
      setConsent({ status: 'error', message: 'No se encontró el ID del usuario.' });
      setBiometria({ status: 'error', message: 'No se encontró el ID del usuario.' });
      return;
    }

    // Carga paralela e independiente de cada sección
    api.obtenerDetalleUsuario(usuarioId)
      .then((data) => setUsuario({ status: 'ok', data }))
      .catch((err) => setUsuario({ status: 'error', message: err instanceof Error ? err.message : String(err) }));

    api.obtenerConsentimientoDeUsuario(usuarioId)
      .then((data) => setConsent({ status: 'ok', data }))
      .catch((err) => setConsent({ status: 'error', message: err instanceof Error ? err.message : String(err) }));

    api.obtenerEstadoBiometriaDeUsuario(usuarioId)
      .then((data) => {
        setBiometria({ status: 'ok', data });
        // Cargar foto si el backend indica que existe
        if (data.tiene_foto) {
          api.obtenerFotoPerfilDeUsuario(usuarioId)
            .then((f) => { if (f) setFoto(f); })
            .catch(() => {});
        }
      })
      .catch((err) => setBiometria({ status: 'error', message: err instanceof Error ? err.message : String(err) }));
  }, [usuarioId]);

  return (
    <StaffShell
      nav={STAFF_NAV}
      title="Detalle del usuario"
      subtitle="Verificación de datos persistidos para un usuario del sistema."
    >
      <div className="space-y-lg animate-in fade-in duration-500">
        {/* Botón volver */}
        <Button
          variant="ghost"
          icon="arrow_back"
          size="sm"
          onClick={() => navigate('/admin/usuarios')}
        >
          Volver a la lista
        </Button>

        {/* ── Sección 1: Datos personales ── */}
        <Card>
          <SectionTitle sub="Información básica del usuario y sus roles en el sistema.">
            Datos personales
          </SectionTitle>

          {usuario.status === 'loading' && <SectionSkeleton />}
          {usuario.status === 'error' && <SectionError message={`No se pudo cargar: ${usuario.message}`} />}
          {usuario.status === 'ok' && (() => {
            const u = usuario.data;
            const nombreDisplay = [u.nombre, u.apellido].filter(Boolean).join(' ') || '—';
            const esBaja = Boolean(u.eliminado_en);
            return (
              <div className="flex flex-col md:flex-row gap-lg">
                {/* Avatar grande */}
                <div className="shrink-0 flex flex-col items-center gap-sm">
                  <div className="w-20 h-20 rounded-2xl bg-secondary-container text-on-secondary flex items-center justify-center font-bold text-[32px] shadow-sm">
                    {(u.nombre ?? u.email).charAt(0).toUpperCase()}
                  </div>
                  <Badge tone={esBaja ? 'error' : 'success'} dot>
                    {esBaja ? 'Dado de baja' : 'Activo'}
                  </Badge>
                </div>

                {/* Datos */}
                <div className="flex-1 min-w-0 divide-y divide-outline-variant/30">
                  <DataRow label="Nombre completo" value={nombreDisplay} />
                  <DataRow label="Email" value={u.email} />
                  <DataRow label="Legajo / ID institucional" value={
                    <span className="font-mono text-[13px]">{u.id_institucional || '—'}</span>
                  } />
                  <DataRow label="Roles" value={
                    u.roles.length > 0
                      ? <div className="flex flex-wrap gap-1">{u.roles.map((r) => <RolBadge key={r} rol={r} />)}</div>
                      : <span className="text-on-surface-variant">Sin roles</span>
                  } />
                  <DataRow label="Proveedor de autenticación" value={
                    <Badge tone="neutral">{u.auth_provider ?? 'local'}</Badge>
                  } />
                  {esBaja && (
                    <DataRow label="Fecha de baja" value={
                      <span className="text-error">{formatFecha(u.eliminado_en)}</span>
                    } />
                  )}
                </div>
              </div>
            );
          })()}
        </Card>

        {/* ── Sección 2: Consentimiento de perfil ── */}
        <Card>
          <SectionTitle sub="Estado del consentimiento informado de perfil del usuario.">
            Consentimiento de perfil
          </SectionTitle>

          {consent.status === 'loading' && <SectionSkeleton />}
          {consent.status === 'error' && <SectionError message={`No se pudo cargar: ${consent.message}`} />}
          {consent.status === 'ok' && (() => {
            const c = consent.data;
            if (!c.estado) {
              return (
                <div className="flex items-center gap-2 text-on-surface-variant bg-surface-container rounded-lg px-3 py-3">
                  <Icon name="info" className="text-[18px] shrink-0" />
                  <span className="text-[13px]">Sin consentimiento registrado para este usuario.</span>
                </div>
              );
            }
            const tone = c.estado === 'otorgado' ? 'success' : 'error';
            return (
              <div className="divide-y divide-outline-variant/30">
                <DataRow label="Estado" value={
                  <Badge tone={tone} dot>
                    {c.estado === 'otorgado' ? 'Otorgado' : 'Revocado'}
                  </Badge>
                } />
                <DataRow label="Versión del texto" value={c.version_texto ?? '—'} />
                <DataRow label="Fecha" value={formatFecha(c.timestamp)} />
                <DataRow label="Hash del texto" value={
                  c.hash_texto
                    ? (
                      <span
                        className="font-mono text-[11px] bg-surface-container px-2 py-0.5 rounded-md truncate max-w-[260px] inline-block"
                        title={c.hash_texto}
                      >
                        {c.hash_texto.slice(0, 28)}…
                      </span>
                    )
                    : '—'
                } />
              </div>
            );
          })()}
        </Card>

        {/* ── Sección 3: Captura de referencia biométrica ── */}
        <Card>
          <SectionTitle sub="Estado de la referencia biométrica facial del usuario.">
            Captura de referencia biométrica
          </SectionTitle>

          {biometria.status === 'loading' && <SectionSkeleton />}
          {biometria.status === 'error' && <SectionError message={`No se pudo cargar: ${biometria.message}`} />}
          {biometria.status === 'ok' && (() => {
            const b = biometria.data;
            return (
              <div className="flex flex-col md:flex-row gap-lg">
                {/* Foto de referencia */}
                <div className="shrink-0 flex flex-col items-center gap-sm">
                  {foto ? (
                    <img
                      src={foto}
                      alt="Foto de referencia biométrica"
                      className="w-28 h-28 rounded-2xl object-cover border border-outline-variant/50 shadow-sm"
                    />
                  ) : (
                    <div className="w-28 h-28 rounded-2xl bg-surface-container-high border border-outline-variant/40 flex flex-col items-center justify-center gap-1 text-on-surface-variant">
                      <Icon name="face" className="text-[32px]" />
                      <span className="text-[11px]">{b.tiene_foto ? 'Cargando…' : 'Sin foto'}</span>
                    </div>
                  )}
                  <span className="text-[11px] text-on-surface-variant">Foto de referencia</span>
                </div>

                {/* Metadatos */}
                <div className="flex-1 min-w-0 divide-y divide-outline-variant/30">
                  <DataRow label="Referencia vigente" value={
                    <Badge tone={b.tiene_referencia_vigente ? 'success' : 'neutral'} dot>
                      {b.tiene_referencia_vigente ? 'Sí' : 'No'}
                    </Badge>
                  } />
                  <DataRow label="Algoritmo" value={b.algoritmo ?? '—'} />
                  <DataRow label="Fecha de creación" value={formatFecha(b.created_at)} />
                  <DataRow label="Fecha de expiración" value={formatFecha(b.fecha_expiracion)} />
                  <DataRow label="Foto registrada" value={
                    <Badge tone={b.tiene_foto ? 'success' : 'neutral'} dot>
                      {b.tiene_foto ? 'Sí' : 'No'}
                    </Badge>
                  } />
                  {b.foto_hash && (
                    <DataRow label="Hash de la foto" value={
                      <span
                        className="font-mono text-[11px] bg-surface-container px-2 py-0.5 rounded-md truncate max-w-[260px] inline-block"
                        title={b.foto_hash}
                      >
                        {b.foto_hash.slice(0, 28)}…
                      </span>
                    } />
                  )}
                  {b.foto_created_at && (
                    <DataRow label="Fecha de la foto" value={formatFecha(b.foto_created_at)} />
                  )}
                </div>
              </div>
            );
          })()}

          <div className="mt-md pt-md border-t border-outline-variant/30">
            <p className="text-[11px] text-on-surface-variant">
              Esta sección permite verificar que la referencia biométrica se persistió correctamente.
              Por seguridad, el dato facial nunca sale del servidor; acá solo ves su estado.
            </p>
          </div>
        </Card>
      </div>
    </StaffShell>
  );
}
