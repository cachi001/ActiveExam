import { useState, useEffect, useCallback } from 'react';
import { Icon, Button, Badge } from '../../../ui/components';
import { ConfirmModal } from '../../../ui/ConfirmModal';
import { useToast } from '../../../ui/toast';
import {
  listarAlumnosDeComision,
  inscribirAlumno,
  eliminarInscripcion,
} from '../../../lib/examContentAdmin';
import type { AlumnoInscripto } from '../../../lib/types';
import { AlumnoPickerModal } from './AlumnoPickerModal';

function nombreAlumno(a: AlumnoInscripto): string {
  const completo = [a.nombre, a.apellido].filter(Boolean).join(' ').trim();
  return completo || a.id_institucional;
}

function CondicionBadge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <Badge tone={ok ? 'success' : 'neutral'} className="text-[11px]">
      <Icon name={ok ? 'check_circle' : 'cancel'} className="text-[14px]" fill />
      {label}
    </Badge>
  );
}

export function AlumnosComisionPanel({
  comisionId,
  comisionNombre,
}: {
  comisionId: string;
  comisionNombre: string;
}) {
  const toast = useToast();
  const [alumnos, setAlumnos] = useState<AlumnoInscripto[] | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pickerAbierto, setPickerAbierto] = useState(false);
  const [inscribiendo, setInscribiendo] = useState(false);
  const [aQuitar, setAQuitar] = useState<AlumnoInscripto | null>(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      const data = await listarAlumnosDeComision(comisionId);
      setAlumnos(data);
    } catch (err) {
      const e = err as Error & { status?: number };
      setError(
        e.status === 404
          ? 'No se encontró la comisión.'
          : 'No se pudieron cargar los alumnos inscriptos.',
      );
      setAlumnos([]);
    } finally {
      setCargando(false);
    }
  }, [comisionId]);

  useEffect(() => { void cargar(); }, [cargar]);

  async function handleInscribir(usuarioId: string) {
    setInscribiendo(true);
    try {
      await inscribirAlumno(comisionId, usuarioId);
      toast.success('Alumno inscripto correctamente.');
      setPickerAbierto(false);
      await cargar();
    } catch (err) {
      const e = err as Error & { status?: number };
      if (e.status === 409) toast.error('Ese alumno ya está inscripto en la comisión.');
      else if (e.status === 404) toast.error('No se encontró la comisión o el alumno.');
      else toast.error('No se pudo inscribir al alumno.');
    } finally {
      setInscribiendo(false);
    }
  }

  async function handleQuitar() {
    if (!aQuitar) return;
    const alumno = aQuitar;
    setAQuitar(null);
    try {
      await eliminarInscripcion(comisionId, alumno.usuario_id);
      toast.success('Inscripción eliminada.');
      await cargar();
    } catch (err) {
      const e = err as Error & { status?: number };
      if (e.status === 404) toast.error('El alumno no estaba inscripto.');
      else toast.error('No se pudo quitar la inscripción.');
    }
  }

  const inscriptosIds = new Set((alumnos ?? []).map((a) => a.usuario_id));

  return (
    <div className="px-8 py-4 bg-surface-container-lowest/60 border-t border-outline-variant/20 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h4 className="text-[12px] font-semibold text-on-surface-variant uppercase tracking-wide flex items-center gap-2">
          <Icon name="groups" className="text-[16px] text-primary" />
          Alumnos inscriptos
          {alumnos && (
            <span className="font-normal normal-case text-on-surface-variant">({alumnos.length})</span>
          )}
        </h4>
        <Button
          variant="primary"
          size="sm"
          icon="person_add"
          onClick={() => setPickerAbierto(true)}
        >
          Inscribir alumno
        </Button>
      </div>

      {cargando ? (
        <div className="py-6 text-center">
          <Icon name="progress_activity" className="ae-spin text-[22px] text-outline" />
        </div>
      ) : error ? (
        <div role="alert" className="flex items-center justify-between gap-xs text-error text-body-sm p-sm rounded-lg bg-error-container">
          <span className="flex items-center gap-xs">
            <Icon name="error" className="text-[18px] shrink-0" fill />
            {error}
          </span>
          <Button variant="ghost" size="sm" onClick={() => void cargar()}>Reintentar</Button>
        </div>
      ) : alumnos && alumnos.length === 0 ? (
        <div className="py-6 text-on-surface-variant text-[13px] flex items-center gap-2">
          <Icon name="info" className="text-[16px] shrink-0" />
          No hay alumnos inscriptos todavía.
        </div>
      ) : alumnos && alumnos.length > 0 ? (
        <ul className="divide-y divide-outline-variant/20 rounded-lg border border-outline-variant/40 overflow-hidden bg-surface">
          {alumnos.map((a) => (
            <li key={a.usuario_id} className="px-3 py-3 flex flex-col sm:flex-row sm:items-center gap-3">
              <div className="flex-1 min-w-0">
                <p className="text-[13px] font-medium text-on-surface truncate">{nombreAlumno(a)}</p>
                <p className="text-[11px] text-on-surface-variant truncate">
                  {a.email}
                  <span className="font-mono"> · {a.id_institucional}</span>
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-1.5 shrink-0">
                <CondicionBadge ok={a.consentimiento_vigente} label="Consentimiento" />
                <CondicionBadge ok={a.biometria_vigente} label="Biometría" />
                {a.puede_rendir ? (
                  <Badge tone="primary" className="text-[11px]">
                    <Icon name="task_alt" className="text-[14px]" fill />
                    Puede rendir
                  </Badge>
                ) : (
                  <span title={a.razon ?? undefined}>
                    <Badge tone="error" className="text-[11px]">
                      <Icon name="block" className="text-[14px]" fill />
                      No puede rendir
                    </Badge>
                  </span>
                )}
              </div>

              <button
                type="button"
                aria-label={`Quitar inscripción de ${nombreAlumno(a)}`}
                onClick={() => setAQuitar(a)}
                className="w-8 h-8 rounded-md flex items-center justify-center text-on-surface-variant hover:bg-error-container hover:text-error transition-colors shrink-0 self-end sm:self-auto"
              >
                <Icon name="person_remove" className="text-[18px]" />
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      {alumnos && alumnos.some((a) => !a.puede_rendir && a.razon) && (
        <ul className="space-y-1">
          {alumnos
            .filter((a) => !a.puede_rendir && a.razon)
            .map((a) => (
              <li key={a.usuario_id} className="text-[11px] text-error flex items-start gap-1.5">
                <Icon name="info" className="text-[13px] shrink-0 mt-0.5" />
                <span><strong>{nombreAlumno(a)}</strong>: {a.razon}</span>
              </li>
            ))}
        </ul>
      )}

      <AlumnoPickerModal
        abierto={pickerAbierto}
        comisionNombre={comisionNombre}
        yaInscriptos={inscriptosIds}
        inscribiendo={inscribiendo}
        onConfirmar={(usuarioId) => void handleInscribir(usuarioId)}
        onCancelar={() => setPickerAbierto(false)}
      />

      <ConfirmModal
        abierto={aQuitar !== null}
        variante="danger"
        titulo="Quitar inscripción"
        mensaje={
          aQuitar ? (
            <>
              ¿Quitar la inscripción de <strong>{nombreAlumno(aQuitar)}</strong> de{' '}
              <strong>{comisionNombre}</strong>?
              <br />
              <span className="text-on-surface-variant text-body-sm">
                El alumno dejará de figurar como inscripto en esta comisión.
              </span>
            </>
          ) : null
        }
        textoConfirmar="Quitar inscripción"
        textoCancelar="Cancelar"
        onConfirmar={() => void handleQuitar()}
        onCancelar={() => setAQuitar(null)}
      />
    </div>
  );
}
