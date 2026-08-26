/**
 * Integración LTI — allowlist de campus Moodle habilitados (c-78 §10.3).
 *
 * Hasta acá esto SOLO existía como API: para habilitar un campus había que armar
 * un PATCH a mano, y la fila se perdía cada vez que se recreaba la base sin que
 * nadie se enterara hasta que un alumno no podía entrar.
 *
 * D16: la pantalla distingue los TRES estados de carga (cargando / cargó vacío /
 * no pudo cargar). Un fallo de red nunca se dibuja como "no hay campus", porque
 * eso invita a registrar de nuevo algo que ya existe.
 */
import { useCallback, useEffect, useState } from 'react';
import { StaffShell } from '../../ui/shells';
import { STAFF_NAV } from '../../ui/nav';
import { Button, Card, Icon, LoadingSpinner, SectionTitle } from '../../ui/components';
import { HelpButton } from '../../ui/HelpButton';
import { RefreshBar } from '../../ui/RefreshBar';
import { ConfirmModal } from '../../ui/ConfirmModal';
import { useToast } from '../../ui/toast';
import { api } from '../../lib/api';
import type { DeploymentLti, SaludLti } from '../../lib/apiAdmin';

function formatFecha(iso: string): string {
  try {
    return new Intl.DateTimeFormat('es-AR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export default function IntegracionLti() {
  const toast = useToast();

  const [salud, setSalud] = useState<SaludLti | null>(null);
  const [campus, setCampus] = useState<DeploymentLti[]>([]);
  const [cargando, setCargando] = useState(true);
  // D16: `error` distinto de `campus.length === 0`. Sin esto, un 401 o una caída
  // se veían idénticos a "todavía no registraste ningún campus".
  const [error, setError] = useState<string | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | undefined>();
  const [operandoId, setOperandoId] = useState<string | null>(null);
  const [pendienteApagar, setPendienteApagar] = useState<DeploymentLti | null>(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      const [saludResp, lista] = await Promise.all([
        api.saludLti(),
        api.listarDeploymentsLti(),
      ]);
      setSalud(saludResp);
      setCampus(lista);
      setLastUpdatedAt(Date.now());
    } catch (err: unknown) {
      const status = (err as { status?: number })?.status;
      setError(
        status === 403
          ? 'No tenés permiso para ver la integración LTI. Es una pantalla solo para administradores.'
          : 'No se pudo cargar la lista de campus. Puede ser la conexión o que el servidor no esté respondiendo. Probá "Actualizar".',
      );
      // No se degrada a lista vacía: eso diría "no hay campus" cuando en realidad
      // no sabemos qué hay.
      setSalud(null);
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  async function cambiarEstado(fila: DeploymentLti, activo: boolean) {
    setOperandoId(fila.id);
    try {
      await api.setActivoDeploymentLti(fila.id, activo);
      toast.success(
        activo
          ? 'Campus habilitado. Los alumnos ya pueden entrar desde ahí.'
          : 'Campus deshabilitado. Sus alumnos no van a poder entrar.',
      );
      await cargar();
    } catch {
      toast.error('No se pudo cambiar el estado del campus. Probá de nuevo.');
    } finally {
      setOperandoId(null);
    }
  }

  const hayCampus = campus.length > 0;

  return (
    <StaffShell
      nav={STAFF_NAV}
      title="Integración LTI"
      subtitle="Campus Moodle habilitados a mandar alumnos a ActiveExam."
      help={
        <HelpButton title="Integración LTI">
          <p>
            Acá figuran los campus virtuales (Moodle) que tienen permiso para mandar
            alumnos a rendir a ActiveExam. Es una lista de permitidos: si un campus
            no está en esta lista y <strong>habilitado</strong>, sus alumnos no
            pueden entrar.
          </p>
          <p>
            <strong>Cómo se agrega un campus.</strong> No hace falta cargarlo a mano.
            El administrador del Moodle registra ActiveExam desde su propio panel
            (opción de "registro dinámico" al agregar una herramienta externa) y el
            campus aparece solo en esta lista, <em>apagado</em>.
          </p>
          <p>
            <strong>Por qué aparece apagado.</strong> A propósito. Que un campus se
            registre no significa que deba tener acceso: alguien de la institución
            tiene que mirarlo y decidir. Ese es el botón "Habilitar".
          </p>
          <p>
            <strong>Si deshabilitás un campus</strong>, sus alumnos dejan de poder
            entrar de inmediato. No se borra nada: los exámenes ya rendidos y sus
            notas quedan tal cual.
          </p>
        </HelpButton>
      }
    >
      <div className="space-y-lg animate-in fade-in duration-500">
        <RefreshBar
          texto="Campus registrados"
          lastUpdatedAt={lastUpdatedAt}
          cargando={cargando}
          onActualizar={cargar}
        />

        {/* Estado general: el aviso que antes no existía en ningún lado. */}
        {salud && (
          <Card>
            <div className="flex items-start gap-3">
              <div
                className={`w-10 h-10 shrink-0 rounded-xl flex items-center justify-center ${
                  salud.allowlist_vacia
                    ? 'bg-error-container text-on-error-container'
                    : 'bg-success-container text-success'
                }`}
              >
                <Icon
                  name={salud.allowlist_vacia ? 'gpp_maybe' : 'verified_user'}
                  className="text-[20px]"
                  fill
                />
              </div>
              <div className="min-w-0">
                <p className="text-[15px] font-semibold text-on-surface">
                  {salud.allowlist_vacia
                    ? 'Nadie puede entrar desde Moodle'
                    : 'La integración está funcionando'}
                </p>
                <p className="text-[13px] text-on-surface-variant mt-0.5">{salud.mensaje}</p>
              </div>
            </div>
          </Card>
        )}

        <Card padded={false}>
          <div className="px-lg py-md border-b border-surface-200">
            <SectionTitle
              icon="lan"
              sub="Cada fila es un campus. Habilitado = sus alumnos pueden entrar."
            >
              Campus registrados
            </SectionTitle>
          </div>

          <div className="px-lg py-md">
            {/* 1. Cargando */}
            {cargando && <LoadingSpinner size="sm" label="Cargando campus…" />}

            {/* 2. No pudo cargar — NUNCA se dibuja como "no hay nada" (D16). */}
            {!cargando && error && (
              <div className="text-center py-xl space-y-base">
                <Icon name="cloud_off" className="text-[40px] text-error" />
                <p className="text-label-md text-on-surface">{error}</p>
                <Button variant="ghost" size="sm" onClick={cargar}>
                  Reintentar
                </Button>
              </div>
            )}

            {/* 3. Cargó y está vacío */}
            {!cargando && !error && !hayCampus && (
              <div className="text-center py-xl text-on-surface-variant space-y-base">
                <Icon name="lan" className="text-[40px] text-outline" />
                <p className="text-label-md">
                  Todavía no hay ningún campus registrado. Pedile al administrador del
                  Moodle que registre ActiveExam desde su panel; cuando lo haga, va a
                  aparecer acá para que lo habilites.
                </p>
              </div>
            )}

            {!cargando && !error && hayCampus && (
              <ul className="divide-y divide-surface-200 -mx-lg">
                {campus.map((c) => (
                  <li key={c.id} className="flex items-start gap-3 px-lg py-4">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-on-surface break-all">{c.iss}</span>
                        <span
                          className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                            c.activo
                              ? 'bg-success-container text-success'
                              : 'bg-surface-200 text-on-surface-variant'
                          }`}
                        >
                          {c.activo ? 'Habilitado' : 'No habilitado'}
                        </span>
                      </div>
                      <p className="text-[12.5px] text-on-surface-variant mt-1 break-all">
                        Identificador del campus: <code>{c.client_id}</code> · Instalación:{' '}
                        <code>{c.deployment_id}</code>
                      </p>
                      <p className="text-[12px] text-outline mt-0.5">
                        Registrado el {formatFecha(c.creado_en)}
                        {c.comision_id
                          ? ' · matricula automáticamente en una comisión'
                          : ' · sin matriculación automática'}
                      </p>
                    </div>
                    <div className="shrink-0">
                      {c.activo ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={operandoId === c.id}
                          onClick={() => setPendienteApagar(c)}
                        >
                          Deshabilitar
                        </Button>
                      ) : (
                        <Button
                          size="sm"
                          disabled={operandoId === c.id}
                          onClick={() => cambiarEstado(c, true)}
                        >
                          Habilitar
                        </Button>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Card>
      </div>

      <ConfirmModal
        abierto={pendienteApagar !== null}
        titulo="Deshabilitar el campus"
        variante="danger"
        textoConfirmar="Deshabilitar"
        mensaje={
          <>
            <p>
              Los alumnos de <strong>{pendienteApagar?.iss}</strong> van a dejar de
              poder entrar a ActiveExam desde su campus, de inmediato.
            </p>
            <p className="mt-2">
              No se borra nada: los exámenes ya rendidos, sus notas y su evidencia
              quedan igual. Podés volver a habilitarlo cuando quieras.
            </p>
          </>
        }
        onConfirmar={() => {
          const fila = pendienteApagar;
          setPendienteApagar(null);
          if (fila) void cambiarEstado(fila, false);
        }}
        onCancelar={() => setPendienteApagar(null)}
      />
    </StaffShell>
  );
}
