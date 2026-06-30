/**
 * MateriasComisiones — gestión admin de materias y comisiones (C-69).
 *
 * Ruta: /admin/materias (roles: admin_sistema)
 *
 * Funcionalidades:
 *  - Listar materias con acordeón de comisiones (carga lazy por materia).
 *  - Crear / editar materia (formulario inline sobre la lista).
 *  - Crear / editar comisión (formulario inline dentro de la sección expandida).
 *
 * Lee datos con api.materiasDisponibles() / api.comisionesDeMateria() que
 * manejan demo-mode. Escribe con crearMateria / actualizarMateria / crearComision /
 * actualizarComision de examContentAdmin (requieren backend real; en modo demo
 * muestran error de red esperado).
 */

import { useEffect, useState, useCallback, useRef, Fragment } from 'react';
import { createPortal } from 'react-dom';
import { StaffShell } from '../ui/shells';
import { Icon, Card, SectionTitle, Button, Badge } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { ActionMenu } from '../ui/ActionMenu';
import { ConfirmModal } from '../ui/ConfirmModal';
import { STAFF_NAV } from '../ui/nav';
import { useToast } from '../ui/toast';
import { api } from '../lib/api';
import {
  crearMateria,
  actualizarMateria,
  crearComision,
  actualizarComision,
  listarAlumnosDeComision,
  inscribirAlumno,
  eliminarInscripcion,
} from '../lib/examContentAdmin';
import type { Materia, Comision, AlumnoInscripto, UsuarioAdmin } from '../lib/types';

// ---------------------------------------------------------------------------
// Clases de input — misma estética que ImportExamModal (border-outline-variant,
// radius chico, focus ring primary).
// ---------------------------------------------------------------------------

const INPUT_CLASS =
  'w-full rounded-md border border-outline-variant bg-surface px-3 py-2.5 text-sm ' +
  'text-on-surface outline-none transition-colors hover:border-outline focus:border-primary ' +
  'focus:ring-1 focus:ring-primary/30 disabled:opacity-50 disabled:cursor-not-allowed';

const LABEL_CLASS = 'block text-xs font-semibold text-on-surface-variant uppercase tracking-wide mb-1';

// ---------------------------------------------------------------------------
// Estado del formulario de materia
// ---------------------------------------------------------------------------

interface FormMateria {
  modo: 'crear' | 'editar';
  id: string | null;         // id de la materia en edición
  codigo: string;
  nombre: string;
}

const FORM_MATERIA_VACIO: FormMateria = { modo: 'crear', id: null, codigo: '', nombre: '' };

// ---------------------------------------------------------------------------
// Estado del formulario de comisión
// ---------------------------------------------------------------------------

interface FormComision {
  modo: 'crear' | 'editar';
  materiaId: string;
  comisionId: string | null;  // id de la comisión en edición
  codigo: string;
  nombre: string;
  periodo: string;
  anio: string;               // string para el input; convertido a number al enviar
}

const FORM_COMISION_VACIO: Omit<FormComision, 'materiaId'> = {
  modo: 'crear',
  comisionId: null,
  codigo: '',
  nombre: '',
  periodo: '',
  anio: '',
};

// ---------------------------------------------------------------------------
// Helpers de error
// ---------------------------------------------------------------------------

function mensajeDeError(
  err: unknown,
  contexto: 'materia' | 'comision',
): string {
  const e = err as Error & { status?: number };
  if (e.status === 409) {
    return contexto === 'materia'
      ? 'Ya existe una materia con ese código.'
      : 'Ya existe una comisión con ese código en esta materia.';
  }
  if (e.status === 422) {
    return 'Datos inválidos. Revisá los campos e intentá de nuevo.';
  }
  if (e.status === 404) {
    return contexto === 'materia'
      ? 'No se encontró la materia.'
      : 'No se encontró la comisión o la materia.';
  }
  if (e.message?.includes('Failed to fetch') || e.message?.includes('fetch')) {
    return 'No se pudo conectar con el servidor. ¿Está activo el backend?';
  }
  return e.message ?? 'Error inesperado.';
}

/** Nombre legible de un alumno: "Nombre Apellido", o el que haya, o el id
 *  institucional como fallback (nunca queda vacío). */
function nombreAlumno(a: AlumnoInscripto): string {
  const completo = [a.nombre, a.apellido].filter(Boolean).join(' ').trim();
  return completo || a.id_institucional;
}

/** Nombre legible de un usuario del picker (rol estudiante). */
function nombreUsuario(u: UsuarioAdmin): string {
  const completo = [u.nombre, u.apellido].filter(Boolean).join(' ').trim();
  return completo || u.id_institucional || u.email;
}

// ---------------------------------------------------------------------------
// Badge de check / cruz para una condición de elegibilidad (consentimiento /
// biometría). Verde con ✔ si está vigente; gris con ✗ si no.
// ---------------------------------------------------------------------------

function CondicionBadge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <Badge tone={ok ? 'success' : 'neutral'} className="text-[11px]">
      <Icon name={ok ? 'check_circle' : 'cancel'} className="text-[14px]" fill />
      {label}
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Picker de alumnos — modal accesible que reusa api.listarUsuarios filtrando por
// rol estudiante. Selección simple + confirmar. Escape y click-afuera cierran.
// ---------------------------------------------------------------------------

interface AlumnoPickerModalProps {
  abierto: boolean;
  comisionNombre: string;
  yaInscriptos: Set<string>;
  inscribiendo: boolean;
  onConfirmar: (usuarioId: string) => void;
  onCancelar: () => void;
}

function AlumnoPickerModal({
  abierto,
  comisionNombre,
  yaInscriptos,
  inscribiendo,
  onConfirmar,
  onCancelar,
}: AlumnoPickerModalProps) {
  const [qInput, setQInput] = useState('');
  const [usuarios, setUsuarios] = useState<UsuarioAdmin[]>([]);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [seleccionado, setSeleccionado] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const cargar = useCallback(async (texto: string) => {
    setCargando(true);
    setError(null);
    try {
      const data = await api.listarUsuarios(50, 0, {
        rol: 'estudiante',
        estado: 'activo',
        q: texto || undefined,
      });
      setUsuarios(data.items);
    } catch {
      setError('No se pudo cargar la lista de estudiantes.');
      setUsuarios([]);
    } finally {
      setCargando(false);
    }
  }, []);

  // Al abrir: reset + carga inicial + foco en el buscador.
  useEffect(() => {
    if (!abierto) return;
    setQInput('');
    setSeleccionado(null);
    void cargar('');
    const t = setTimeout(() => inputRef.current?.focus(), 50);
    return () => clearTimeout(t);
  }, [abierto, cargar]);

  // Escape cierra el picker.
  useEffect(() => {
    if (!abierto) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancelar();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [abierto, onCancelar]);

  if (!abierto) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-md bg-black/40 animate-in fade-in"
      onClick={onCancelar}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="picker-alumno-titulo"
        className="w-full max-w-lg bg-surface-container-lowest rounded-2xl shadow-card-lg
          border border-outline-variant/40 p-lg space-y-md animate-in zoom-in fade-in flex flex-col max-h-[80vh]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="space-y-base">
          <h2 id="picker-alumno-titulo" className="font-headline text-title-lg text-on-surface tracking-tight">
            Inscribir alumno
          </h2>
          <p className="text-body-sm text-on-surface-variant">
            Elegí un estudiante para inscribir en <strong>{comisionNombre}</strong>.
          </p>
        </div>

        {/* Buscador */}
        <div className="relative">
          <Icon name="search" className="text-[16px] text-on-surface-variant absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            ref={inputRef}
            type="search"
            aria-label="Buscar estudiante por nombre, email o legajo"
            placeholder="Buscar por nombre, email o legajo… (Enter)"
            value={qInput}
            onChange={(e) => {
              const v = e.target.value;
              setQInput(v);
              if (!v) void cargar('');
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                void cargar(qInput);
              }
            }}
            className={INPUT_CLASS + ' pl-8'}
          />
        </div>

        {/* Listado de estudiantes */}
        <div className="flex-1 overflow-y-auto -mx-1 px-1 min-h-[120px]">
          {cargando ? (
            <div className="py-8 text-center">
              <Icon name="progress_activity" className="ae-spin text-[24px] text-outline" />
            </div>
          ) : error ? (
            <div role="alert" className="flex items-center gap-xs text-error text-body-sm p-sm rounded-lg bg-error-container">
              <Icon name="error" className="text-[18px] shrink-0" fill />
              {error}
            </div>
          ) : usuarios.length === 0 ? (
            <p className="py-8 text-center text-on-surface-variant text-[13px]">
              No se encontraron estudiantes con esa búsqueda.
            </p>
          ) : (
            <ul className="space-y-1" role="listbox" aria-label="Estudiantes disponibles">
              {usuarios.map((u) => {
                const inscripto = yaInscriptos.has(u.id);
                const elegido = seleccionado === u.id;
                return (
                  <li key={u.id}>
                    <button
                      type="button"
                      role="option"
                      aria-selected={elegido}
                      disabled={inscripto || inscribiendo}
                      onClick={() => setSeleccionado(u.id)}
                      className={`w-full text-left flex items-center gap-3 px-3 py-2.5 rounded-lg border transition-colors
                        disabled:opacity-50 disabled:cursor-not-allowed
                        ${elegido
                          ? 'border-primary bg-primary/5'
                          : 'border-outline-variant hover:border-outline hover:bg-surface-container-low'}`}
                    >
                      <div className="w-8 h-8 rounded-full bg-secondary-container text-on-secondary flex items-center justify-center font-semibold text-[13px] shrink-0">
                        {nombreUsuario(u).charAt(0).toUpperCase()}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-[13px] font-medium text-on-surface truncate">{nombreUsuario(u)}</p>
                        <p className="text-[11px] text-on-surface-variant truncate">
                          {u.email}
                          <span className="font-mono"> · {u.id_institucional}</span>
                        </p>
                      </div>
                      {inscripto ? (
                        <span className="text-[11px] text-on-surface-variant shrink-0">Ya inscripto</span>
                      ) : elegido ? (
                        <Icon name="check_circle" className="text-[18px] text-primary shrink-0" fill />
                      ) : null}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <div className="flex items-center justify-end gap-sm pt-base border-t border-outline-variant/40">
          <Button variant="ghost" size="sm" onClick={onCancelar} disabled={inscribiendo}>
            Cancelar
          </Button>
          <Button
            variant="primary"
            size="sm"
            disabled={!seleccionado || inscribiendo}
            onClick={() => seleccionado && onConfirmar(seleccionado)}
          >
            {inscribiendo ? (
              <span className="inline-flex items-center gap-xs">
                <Icon name="progress_activity" className="ae-spin text-[18px]" />
                Inscribiendo…
              </span>
            ) : 'Inscribir'}
          </Button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

// ---------------------------------------------------------------------------
// Panel de alumnos inscriptos de una comisión. Se monta SOLO al expandir la
// comisión (carga lazy): el primer render dispara la carga de alumnos.
// ---------------------------------------------------------------------------

function AlumnosComisionPanel({
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

  // Carga lazy: el panel se monta al expandir la comisión.
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
      {/* Cabecera del panel */}
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

      {/* Estados */}
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
              {/* Identidad */}
              <div className="flex-1 min-w-0">
                <p className="text-[13px] font-medium text-on-surface truncate">{nombreAlumno(a)}</p>
                <p className="text-[11px] text-on-surface-variant truncate">
                  {a.email}
                  <span className="font-mono"> · {a.id_institucional}</span>
                </p>
              </div>

              {/* Elegibilidad */}
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

              {/* Acción: quitar */}
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

      {/* Razón de "no puede rendir" — visible (no solo en title) para los que no pueden */}
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

      {/* Picker de inscripción */}
      <AlumnoPickerModal
        abierto={pickerAbierto}
        comisionNombre={comisionNombre}
        yaInscriptos={inscriptosIds}
        inscribiendo={inscribiendo}
        onConfirmar={(usuarioId) => void handleInscribir(usuarioId)}
        onCancelar={() => setPickerAbierto(false)}
      />

      {/* Confirmación de quita de inscripción */}
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

// ---------------------------------------------------------------------------
// Componente principal
// ---------------------------------------------------------------------------

export default function MateriasComisiones() {
  const toast = useToast();

  // ── Materias ──────────────────────────────────────────────────────────────
  const [materias, setMaterias] = useState<Materia[]>([]);
  const [cargandoMaterias, setCargandoMaterias] = useState(true);

  // ── Acordeón ──────────────────────────────────────────────────────────────
  const [expandida, setExpandida] = useState<string | null>(null);
  const [comisionesPorMateria, setComisionesPorMateria] = useState<Record<string, Comision[]>>({});
  const [cargandoComisiones, setCargandoComisiones] = useState<Record<string, boolean>>({});

  // ── Comisión expandida (para ver/gestionar alumnos inscriptos) ─────────────
  const [comisionExpandida, setComisionExpandida] = useState<string | null>(null);

  function toggleComision(comisionId: string) {
    setComisionExpandida((prev) => (prev === comisionId ? null : comisionId));
  }

  // ── Formulario de materia ─────────────────────────────────────────────────
  const [formMateria, setFormMateria] = useState<FormMateria | null>(null);
  const [errorFormMateria, setErrorFormMateria] = useState<string | null>(null);
  const [enviandoMateria, setEnviandoMateria] = useState(false);
  const primerInputMateriaRef = useRef<HTMLInputElement>(null);

  // ── Formulario de comisión ────────────────────────────────────────────────
  const [formComision, setFormComision] = useState<FormComision | null>(null);
  const [errorFormComision, setErrorFormComision] = useState<string | null>(null);
  const [enviandoComision, setEnviandoComision] = useState(false);
  const primerInputComisionRef = useRef<HTMLInputElement>(null);
  const [periodos, setPeriodos] = useState<{ value: string; label: string }[]>([
    { value: '1C', label: '1er cuatrimestre' },
    { value: '2C', label: '2do cuatrimestre' },
  ]);

  useEffect(() => {
    api.listarPeriodos().then(setPeriodos).catch(() => {/* usa fallback */});
  }, []);

  // ── Carga inicial de materias ─────────────────────────────────────────────

  const cargarMaterias = useCallback(async () => {
    setCargandoMaterias(true);
    try {
      const data = await api.materiasDisponibles();
      setMaterias(data);
    } catch {
      toast.error('No se pudo cargar la lista de materias.');
    } finally {
      setCargandoMaterias(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { void cargarMaterias(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Escape cierra el formulario activo
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      if (formMateria) cerrarFormMateria();
      else if (formComision) cerrarFormComision();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formMateria, formComision]);

  // ── Acordeón ──────────────────────────────────────────────────────────────

  async function toggleExpand(materiaId: string) {
    if (expandida === materiaId) {
      setExpandida(null);
      // Limpiar formulario de comision si corresponde a esta materia
      if (formComision?.materiaId === materiaId) cerrarFormComision();
      return;
    }

    setExpandida(materiaId);

    // Carga lazy de comisiones
    if (!comisionesPorMateria[materiaId]) {
      setCargandoComisiones((prev) => ({ ...prev, [materiaId]: true }));
      try {
        const data = await api.comisionesDeMateria(materiaId);
        setComisionesPorMateria((prev) => ({ ...prev, [materiaId]: data }));
      } catch {
        toast.error('No se pudieron cargar las comisiones.');
        setComisionesPorMateria((prev) => ({ ...prev, [materiaId]: [] }));
      } finally {
        setCargandoComisiones((prev) => ({ ...prev, [materiaId]: false }));
      }
    }
  }

  // ── Formulario de materia ─────────────────────────────────────────────────

  function abrirCrearMateria() {
    setFormMateria({ ...FORM_MATERIA_VACIO, modo: 'crear' });
    setErrorFormMateria(null);
    setTimeout(() => primerInputMateriaRef.current?.focus(), 50);
  }

  function abrirEditarMateria(m: Materia) {
    setFormMateria({ modo: 'editar', id: m.id, codigo: m.codigo, nombre: m.nombre });
    setErrorFormMateria(null);
    setTimeout(() => primerInputMateriaRef.current?.focus(), 50);
  }

  function cerrarFormMateria() {
    setFormMateria(null);
    setErrorFormMateria(null);
  }

  async function handleSubmitMateria(e: React.FormEvent) {
    e.preventDefault();
    if (!formMateria) return;

    setErrorFormMateria(null);
    setEnviandoMateria(true);

    try {
      if (formMateria.modo === 'crear') {
        const nueva = await crearMateria({ codigo: formMateria.codigo, nombre: formMateria.nombre });
        setMaterias((prev) => [...prev, { ...nueva }]);
        toast.success('Materia creada correctamente.');
      } else if (formMateria.modo === 'editar' && formMateria.id) {
        const actualizada = await actualizarMateria(formMateria.id, { nombre: formMateria.nombre });
        setMaterias((prev) =>
          prev.map((m) => (m.id === formMateria.id ? { ...m, nombre: actualizada.nombre } : m)),
        );
        toast.success('Materia actualizada correctamente.');
      }
      cerrarFormMateria();
    } catch (err) {
      setErrorFormMateria(mensajeDeError(err, 'materia'));
    } finally {
      setEnviandoMateria(false);
    }
  }

  // ── Formulario de comisión ────────────────────────────────────────────────

  function abrirCrearComision(materiaId: string) {
    // Asegurar que la materia esté expandida
    if (expandida !== materiaId) {
      void toggleExpand(materiaId);
    }
    setFormComision({ ...FORM_COMISION_VACIO, modo: 'crear', materiaId });
    setErrorFormComision(null);
    setTimeout(() => primerInputComisionRef.current?.focus(), 80);
  }

  function abrirEditarComision(materiaId: string, c: Comision) {
    if (expandida !== materiaId) {
      void toggleExpand(materiaId);
    }
    setFormComision({
      modo: 'editar',
      materiaId,
      comisionId: c.id,
      codigo: c.codigo ?? '',
      nombre: c.nombre,
      periodo: c.periodo ?? '',
      anio: c.anio != null ? String(c.anio) : '',
    });
    setErrorFormComision(null);
    setTimeout(() => primerInputComisionRef.current?.focus(), 80);
  }

  function cerrarFormComision() {
    setFormComision(null);
    setErrorFormComision(null);
  }

  async function handleSubmitComision(e: React.FormEvent) {
    e.preventDefault();
    if (!formComision) return;

    setErrorFormComision(null);
    setEnviandoComision(true);

    const anioNum = formComision.anio ? parseInt(formComision.anio, 10) : null;
    const periodoVal = formComision.periodo.trim() || null;

    try {
      if (formComision.modo === 'crear') {
        const nueva = await crearComision(formComision.materiaId, {
          codigo: formComision.codigo,
          nombre: formComision.nombre,
          periodo: periodoVal,
          anio: anioNum,
        });
        // Agregar al map de comisiones del acordeón
        setComisionesPorMateria((prev) => ({
          ...prev,
          [formComision.materiaId]: [...(prev[formComision.materiaId] ?? []), { ...nueva }],
        }));
        toast.success('Comisión creada correctamente.');
      } else if (formComision.modo === 'editar' && formComision.comisionId) {
        const actualizada = await actualizarComision(formComision.comisionId, {
          nombre: formComision.nombre,
          periodo: periodoVal,
          anio: anioNum,
        });
        setComisionesPorMateria((prev) => {
          const list = prev[formComision.materiaId] ?? [];
          return {
            ...prev,
            [formComision.materiaId]: list.map((c) =>
              c.id === formComision.comisionId
                ? { ...c, nombre: actualizada.nombre, periodo: actualizada.periodo, anio: actualizada.anio }
                : c,
            ),
          };
        });
        toast.success('Comisión actualizada correctamente.');
      }
      cerrarFormComision();
    } catch (err) {
      setErrorFormComision(mensajeDeError(err, 'comision'));
    } finally {
      setEnviandoComision(false);
    }
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <StaffShell
      nav={STAFF_NAV}
      title="Materias y comisiones"
      subtitle="Creá y gestioná materias y sus comisiones de cursado."
      help={
        <HelpButton title="Materias y comisiones">
          <p>
            Desde acá podés crear materias y agregar comisiones a cada una. Las comisiones
            se usan para asociar exámenes importados al catálogo de cursado.
          </p>
          <p>
            Hacé clic en una materia para expandirla y ver o agregar comisiones.
            La asociación examen↔comisión sigue siendo opcional (D11).
          </p>
        </HelpButton>
      }
      actions={
        <Button icon="add" onClick={abrirCrearMateria} size="sm">
          Nueva materia
        </Button>
      }
    >
      <div className="space-y-lg animate-in fade-in duration-500">

        {/* ── Formulario de materia (crear / editar) ──────────────────────── */}
        {formMateria && (
          <Card>
            <SectionTitle>
              {formMateria.modo === 'crear' ? 'Nueva materia' : 'Editar materia'}
            </SectionTitle>
            <form onSubmit={handleSubmitMateria} className="space-y-md mt-md">
              <div className="grid sm:grid-cols-2 gap-md">
                {formMateria.modo === 'crear' && (
                  <div>
                    <label htmlFor="materia-codigo" className={LABEL_CLASS}>
                      Código <span aria-hidden="true">*</span>
                    </label>
                    <input
                      ref={primerInputMateriaRef}
                      id="materia-codigo"
                      name="materia-codigo"
                      type="text"
                      required
                      disabled={enviandoMateria}
                      placeholder="Ej. CB101"
                      value={formMateria.codigo}
                      onChange={(e) =>
                        setFormMateria((prev) => prev ? { ...prev, codigo: e.target.value } : prev)
                      }
                      className={INPUT_CLASS}
                    />
                  </div>
                )}
                <div className={formMateria.modo === 'editar' ? 'sm:col-span-2' : ''}>
                  <label htmlFor="materia-nombre" className={LABEL_CLASS}>
                    Nombre <span aria-hidden="true">*</span>
                  </label>
                  <input
                    ref={formMateria.modo === 'editar' ? primerInputMateriaRef : undefined}
                    id="materia-nombre"
                    name="materia-nombre"
                    type="text"
                    required
                    disabled={enviandoMateria}
                    placeholder="Ej. Análisis Matemático I"
                    value={formMateria.nombre}
                    onChange={(e) =>
                      setFormMateria((prev) => prev ? { ...prev, nombre: e.target.value } : prev)
                    }
                    className={INPUT_CLASS}
                  />
                </div>
              </div>

              {errorFormMateria && (
                <div
                  role="alert"
                  className="flex items-center gap-xs text-error text-body-sm p-sm rounded-lg bg-error-container"
                >
                  <Icon name="error" className="text-[18px] shrink-0" fill />
                  {errorFormMateria}
                </div>
              )}

              <div className="flex gap-sm justify-end">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={cerrarFormMateria}
                  disabled={enviandoMateria}
                >
                  Cancelar
                </Button>
                <Button type="submit" disabled={enviandoMateria}>
                  {enviandoMateria ? (
                    <span className="inline-flex items-center gap-xs">
                      <Icon name="progress_activity" className="ae-spin text-[20px]" />
                      Guardando…
                    </span>
                  ) : formMateria.modo === 'crear' ? 'Crear materia' : 'Guardar cambios'}
                </Button>
              </div>
            </form>
          </Card>
        )}

        {/* ── Lista de materias con acordeón ──────────────────────────────── */}
        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/60 shadow-card overflow-hidden">
          {/* Cabecera */}
          <div className="px-4 py-3 border-b border-outline-variant/40 flex items-center gap-2">
            <Icon name="school" className="text-[16px] text-primary shrink-0" />
            <h2 className="text-[13px] font-semibold text-on-surface">
              Materias
              {!cargandoMaterias && (
                <span className="text-on-surface-variant font-normal ml-1">({materias.length})</span>
              )}
            </h2>
          </div>

          {/* Carga */}
          {cargandoMaterias ? (
            <div className="py-12 text-center text-on-surface-variant">
              <Icon name="progress_activity" className="ae-spin text-[28px] text-outline" />
            </div>
          ) : materias.length === 0 ? (
            /* Vacío */
            <div className="py-12 text-center text-on-surface-variant space-y-base">
              <Icon name="school" className="text-[36px] text-outline" />
              <p className="text-[13px]">No hay materias registradas. Creá la primera usando el botón de arriba.</p>
            </div>
          ) : (
            /* Lista */
            <div className="divide-y divide-outline-variant/30">
              {materias.map((m) => {
                const estaExpandida = expandida === m.id;
                const comisiones = comisionesPorMateria[m.id];
                const cargando = cargandoComisiones[m.id];
                const mostrarFormComision = formComision?.materiaId === m.id;

                return (
                  <div key={m.id}>
                    {/* ── Fila de materia ──────────────────────────────── */}
                    <div className="flex items-center gap-3 px-4 py-3.5 hover:bg-surface-container-low transition-colors group">
                      {/* Botón de expansión */}
                      <button
                        type="button"
                        aria-label={estaExpandida ? `Colapsar ${m.nombre}` : `Expandir ${m.nombre}`}
                        aria-expanded={estaExpandida}
                        onClick={() => void toggleExpand(m.id)}
                        className="w-7 h-7 rounded-md flex items-center justify-center text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors shrink-0"
                      >
                        <Icon
                          name={estaExpandida ? 'keyboard_arrow_down' : 'keyboard_arrow_right'}
                          className="text-[20px]"
                        />
                      </button>

                      {/* Icono de materia */}
                      <div className="w-8 h-8 rounded-lg bg-primary-fixed text-on-primary-fixed-variant flex items-center justify-center shrink-0">
                        <Icon name="school" className="text-[16px]" />
                      </div>

                      {/* Datos */}
                      <div className="flex-1 min-w-0">
                        <button
                          type="button"
                          onClick={() => void toggleExpand(m.id)}
                          className="text-[13px] font-semibold text-on-surface group-hover:text-primary transition-colors truncate text-left w-full"
                        >
                          {m.nombre}
                        </button>
                        <p className="text-[11px] font-mono text-on-surface-variant mt-0.5">
                          {m.codigo}
                        </p>
                      </div>

                      {/* Acciones */}
                      <ActionMenu
                        ariaLabel={`Acciones de ${m.nombre}`}
                        items={[
                          {
                            label: 'Editar materia',
                            icon: 'edit',
                            onClick: () => abrirEditarMateria(m),
                          },
                          {
                            label: 'Nueva comisión',
                            icon: 'add_circle',
                            onClick: () => abrirCrearComision(m.id),
                          },
                        ]}
                      />
                    </div>

                    {/* ── Sección expandida: comisiones ─────────────────── */}
                    {estaExpandida && (
                      <div className="bg-surface-container-low border-t border-outline-variant/20">

                        {/* Formulario de comisión */}
                        {mostrarFormComision && formComision && (
                          <div className="px-4 pt-4 pb-3">
                            <p className="text-[12px] font-semibold text-on-surface-variant uppercase tracking-wide mb-3">
                              {formComision.modo === 'crear' ? 'Nueva comisión' : 'Editar comisión'}
                            </p>
                            <form onSubmit={handleSubmitComision} className="space-y-3">
                              <div className="grid sm:grid-cols-2 md:grid-cols-4 gap-3">
                                {formComision.modo === 'crear' && (
                                  <div>
                                    <label htmlFor="comision-codigo" className={LABEL_CLASS}>
                                      Código <span aria-hidden="true">*</span>
                                    </label>
                                    <input
                                      ref={primerInputComisionRef}
                                      id="comision-codigo"
                                      name="comision-codigo"
                                      type="text"
                                      required
                                      disabled={enviandoComision}
                                      placeholder="Ej. 1A"
                                      value={formComision.codigo}
                                      onChange={(e) =>
                                        setFormComision((prev) =>
                                          prev ? { ...prev, codigo: e.target.value } : prev,
                                        )
                                      }
                                      className={INPUT_CLASS}
                                    />
                                  </div>
                                )}
                                <div className={formComision.modo === 'editar' ? 'sm:col-span-2' : ''}>
                                  <label htmlFor="comision-nombre" className={LABEL_CLASS}>
                                    Nombre <span aria-hidden="true">*</span>
                                  </label>
                                  <input
                                    ref={formComision.modo === 'editar' ? primerInputComisionRef : undefined}
                                    id="comision-nombre"
                                    name="comision-nombre"
                                    type="text"
                                    required
                                    disabled={enviandoComision}
                                    placeholder="Ej. Comisión 1A"
                                    value={formComision.nombre}
                                    onChange={(e) =>
                                      setFormComision((prev) =>
                                        prev ? { ...prev, nombre: e.target.value } : prev,
                                      )
                                    }
                                    className={INPUT_CLASS}
                                  />
                                </div>
                                <div>
                                  <label htmlFor="comision-periodo" className={LABEL_CLASS}>
                                    Período
                                  </label>
                                  <select
                                    id="comision-periodo"
                                    name="comision-periodo"
                                    disabled={enviandoComision}
                                    value={formComision.periodo}
                                    onChange={(e) =>
                                      setFormComision((prev) =>
                                        prev ? { ...prev, periodo: e.target.value } : prev,
                                      )
                                    }
                                    className={INPUT_CLASS}
                                  >
                                    <option value="">Seleccionar...</option>
                                    {periodos.map((p) => (
                                      <option key={p.value} value={p.value}>{p.label}</option>
                                    ))}
                                  </select>
                                </div>
                                <div>
                                  <label htmlFor="comision-anio" className={LABEL_CLASS}>
                                    Año
                                  </label>
                                  <input
                                    id="comision-anio"
                                    name="comision-anio"
                                    type="number"
                                    min={2000}
                                    max={2100}
                                    disabled={enviandoComision}
                                    placeholder="Ej. 2026"
                                    value={formComision.anio}
                                    onChange={(e) =>
                                      setFormComision((prev) =>
                                        prev ? { ...prev, anio: e.target.value } : prev,
                                      )
                                    }
                                    className={INPUT_CLASS}
                                  />
                                </div>
                              </div>

                              {errorFormComision && (
                                <div
                                  role="alert"
                                  className="flex items-center gap-xs text-error text-body-sm p-sm rounded-lg bg-error-container"
                                >
                                  <Icon name="error" className="text-[18px] shrink-0" fill />
                                  {errorFormComision}
                                </div>
                              )}

                              <div className="flex gap-sm justify-end">
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="sm"
                                  onClick={cerrarFormComision}
                                  disabled={enviandoComision}
                                >
                                  Cancelar
                                </Button>
                                <Button type="submit" size="sm" disabled={enviandoComision}>
                                  {enviandoComision ? (
                                    <span className="inline-flex items-center gap-xs">
                                      <Icon name="progress_activity" className="ae-spin text-[18px]" />
                                      Guardando…
                                    </span>
                                  ) : formComision.modo === 'crear' ? 'Crear comisión' : 'Guardar'}
                                </Button>
                              </div>
                            </form>
                          </div>
                        )}

                        {/* Tabla de comisiones */}
                        {cargando ? (
                          <div className="py-6 text-center">
                            <Icon name="progress_activity" className="ae-spin text-[22px] text-outline" />
                          </div>
                        ) : comisiones && comisiones.length === 0 && !mostrarFormComision ? (
                          <div className="py-6 px-8 text-on-surface-variant text-[13px] flex items-center gap-2">
                            <Icon name="info" className="text-[16px] shrink-0" />
                            No hay comisiones todavía.
                            <button
                              type="button"
                              onClick={() => abrirCrearComision(m.id)}
                              className="text-primary hover:underline font-medium ml-1"
                            >
                              Agregar la primera
                            </button>
                          </div>
                        ) : comisiones && comisiones.length > 0 ? (
                          <>
                            {/* Tabla desktop */}
                            <div className="hidden sm:block overflow-x-auto">
                              <table className="w-full">
                                <thead>
                                  <tr className="bg-surface-container">
                                    <th className="text-left text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-8 py-2">
                                      Código
                                    </th>
                                    <th className="text-left text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-4 py-2">
                                      Nombre
                                    </th>
                                    <th className="text-left text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-4 py-2">
                                      Período
                                    </th>
                                    <th className="text-left text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-4 py-2">
                                      Año
                                    </th>
                                    <th className="text-right text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-4 py-2">
                                      Acciones
                                    </th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-outline-variant/20">
                                  {comisiones.map((c) => {
                                    const comExpandida = comisionExpandida === c.id;
                                    return (
                                    <Fragment key={c.id}>
                                    <tr className="hover:bg-surface-container/50 transition-colors">
                                      <td className="px-8 py-3 whitespace-nowrap">
                                        <div className="flex items-center gap-2">
                                          <button
                                            type="button"
                                            aria-label={comExpandida ? `Ocultar alumnos de ${c.nombre}` : `Ver alumnos de ${c.nombre}`}
                                            aria-expanded={comExpandida}
                                            onClick={() => toggleComision(c.id)}
                                            className="w-6 h-6 rounded-md flex items-center justify-center text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors shrink-0"
                                          >
                                            <Icon
                                              name={comExpandida ? 'keyboard_arrow_down' : 'keyboard_arrow_right'}
                                              className="text-[18px]"
                                            />
                                          </button>
                                          <span className="font-mono text-[12px] text-on-surface-variant bg-surface-container px-2 py-0.5 rounded-md">
                                            {c.codigo ?? '—'}
                                          </span>
                                        </div>
                                      </td>
                                      <td className="px-4 py-3 text-[13px] text-on-surface">
                                        {c.nombre}
                                      </td>
                                      <td className="px-4 py-3 text-[13px] text-on-surface-variant">
                                        {c.periodo ?? '—'}
                                      </td>
                                      <td className="px-4 py-3 text-[13px] text-on-surface-variant tabular-nums">
                                        {c.anio ?? '—'}
                                      </td>
                                      <td className="px-4 py-3 text-right">
                                        <ActionMenu
                                          ariaLabel={`Acciones de ${c.nombre}`}
                                          items={[
                                            {
                                              label: comExpandida ? 'Ocultar alumnos' : 'Ver alumnos',
                                              icon: 'groups',
                                              onClick: () => toggleComision(c.id),
                                            },
                                            {
                                              label: 'Editar comisión',
                                              icon: 'edit',
                                              onClick: () => abrirEditarComision(m.id, c),
                                            },
                                          ]}
                                        />
                                      </td>
                                    </tr>
                                    {comExpandida && (
                                      <tr>
                                        <td colSpan={5} className="p-0">
                                          <AlumnosComisionPanel comisionId={c.id} comisionNombre={c.nombre} />
                                        </td>
                                      </tr>
                                    )}
                                    </Fragment>
                                    );
                                  })}
                                </tbody>
                              </table>
                            </div>

                            {/* Cards mobile */}
                            <div className="sm:hidden divide-y divide-outline-variant/20">
                              {comisiones.map((c) => {
                                const comExpandida = comisionExpandida === c.id;
                                return (
                                <div key={c.id}>
                                  <div className="px-8 py-3 flex items-center justify-between gap-3">
                                    <button
                                      type="button"
                                      aria-label={comExpandida ? `Ocultar alumnos de ${c.nombre}` : `Ver alumnos de ${c.nombre}`}
                                      aria-expanded={comExpandida}
                                      onClick={() => toggleComision(c.id)}
                                      className="w-6 h-6 rounded-md flex items-center justify-center text-on-surface-variant hover:bg-surface-container shrink-0"
                                    >
                                      <Icon
                                        name={comExpandida ? 'keyboard_arrow_down' : 'keyboard_arrow_right'}
                                        className="text-[18px]"
                                      />
                                    </button>
                                    <div className="min-w-0 flex-1">
                                      <p className="text-[13px] font-medium text-on-surface truncate">{c.nombre}</p>
                                      <p className="text-[11px] text-on-surface-variant font-mono mt-0.5">
                                        {c.codigo ?? '—'}
                                        {c.periodo ? ` · ${c.periodo}` : ''}
                                        {c.anio ? ` · ${c.anio}` : ''}
                                      </p>
                                    </div>
                                    <ActionMenu
                                      ariaLabel={`Acciones de ${c.nombre}`}
                                      items={[
                                        {
                                          label: comExpandida ? 'Ocultar alumnos' : 'Ver alumnos',
                                          icon: 'groups',
                                          onClick: () => toggleComision(c.id),
                                        },
                                        {
                                          label: 'Editar comisión',
                                          icon: 'edit',
                                          onClick: () => abrirEditarComision(m.id, c),
                                        },
                                      ]}
                                    />
                                  </div>
                                  {comExpandida && (
                                    <AlumnosComisionPanel comisionId={c.id} comisionNombre={c.nombre} />
                                  )}
                                </div>
                                );
                              })}
                            </div>
                          </>
                        ) : null}

                        {/* Botón "Nueva comisión" al pie de la sección */}
                        {comisiones && comisiones.length > 0 && !mostrarFormComision && (
                          <div className="px-8 py-3 border-t border-outline-variant/20">
                            <Button
                              variant="ghost"
                              size="sm"
                              icon="add"
                              onClick={() => abrirCrearComision(m.id)}
                            >
                              Nueva comisión
                            </Button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </StaffShell>
  );
}
