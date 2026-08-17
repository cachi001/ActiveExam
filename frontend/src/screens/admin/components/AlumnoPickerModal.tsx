import { useState, useEffect, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Icon, Button } from '../../../ui/components';
import { api } from '../../../lib/api';
import type { UsuarioAdmin } from '../../../lib/types';

const PAGE_SIZE = 12;

// Input moderno (fondo blanco, focus gris — sin azul).
const INPUT_CLASS =
  'w-full rounded-lg border border-surface-300 bg-white pl-8 pr-3 py-2.5 text-sm shadow-sm ' +
  'text-on-surface transition-colors hover:border-surface-400 focus:border-surface-500 focus:outline-none';

function nombreUsuario(u: UsuarioAdmin): string {
  const completo = [u.nombre, u.apellido].filter(Boolean).join(' ').trim();
  return completo || u.username || u.email;
}

export interface AlumnoPickerModalProps {
  abierto: boolean;
  comisionNombre: string;
  yaInscriptos: Set<string>;
  inscribiendo: boolean;
  /** Inscribe TODOS los seleccionados de una. */
  onConfirmar: (usuarioIds: string[]) => void;
  onCancelar: () => void;
}

export function AlumnoPickerModal({
  abierto,
  comisionNombre,
  yaInscriptos,
  inscribiendo,
  onConfirmar,
  onCancelar,
}: AlumnoPickerModalProps) {
  const [qInput, setQInput] = useState('');
  const [qAplicada, setQAplicada] = useState('');
  const [offset, setOffset] = useState(0);
  const [usuarios, setUsuarios] = useState<UsuarioAdmin[]>([]);
  const [total, setTotal] = useState(0);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Selección MÚLTIPLE y PERSISTENTE: se mantiene aunque cambies de página o
  // busques otra cosa (solo se limpia al abrir/cerrar el modal).
  const [seleccionados, setSeleccionados] = useState<Set<string>>(new Set());
  const inputRef = useRef<HTMLInputElement>(null);

  const cargar = useCallback(async (texto: string, off: number) => {
    setCargando(true);
    setError(null);
    try {
      const data = await api.listarUsuarios(PAGE_SIZE, off, {
        rol: 'estudiante',
        estado: 'activo',
        q: texto || undefined,
      });
      setUsuarios(data.items);
      setTotal(data.total);
    } catch {
      setError('No se pudo cargar la lista de estudiantes.');
      setUsuarios([]);
      setTotal(0);
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    if (!abierto) return;
    setQInput('');
    setQAplicada('');
    setOffset(0);
    setSeleccionados(new Set());
    void cargar('', 0);
    const t = setTimeout(() => inputRef.current?.focus(), 50);
    return () => clearTimeout(t);
  }, [abierto, cargar]);

  useEffect(() => {
    if (!abierto) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancelar();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [abierto, onCancelar]);

  if (!abierto) return null;

  const aplicarBusqueda = () => {
    setQAplicada(qInput);
    setOffset(0);
    void cargar(qInput, 0);
  };

  const irAPagina = (nuevoOffset: number) => {
    setOffset(nuevoOffset);
    void cargar(qAplicada, nuevoOffset);
  };

  const toggle = (id: string) => {
    setSeleccionados((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const paginaActual = Math.floor(offset / PAGE_SIZE) + 1;
  const totalPaginas = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const cantSel = seleccionados.size;

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
          border border-outline-variant/40 p-lg space-y-md animate-in zoom-in fade-in flex flex-col max-h-[85vh]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="space-y-base">
          <h2 id="picker-alumno-titulo" className="font-headline text-title-lg text-on-surface tracking-tight">
            Inscribir alumnos
          </h2>
          <p className="text-body-sm text-on-surface-variant">
            Buscá y seleccioná varios estudiantes para inscribir en <strong>{comisionNombre}</strong>.
            La selección se mantiene aunque cambies de página o de búsqueda.
          </p>
        </div>

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
              if (!v && qAplicada) {
                setQAplicada('');
                setOffset(0);
                void cargar('', 0);
              }
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                aplicarBusqueda();
              }
            }}
            className={INPUT_CLASS}
          />
        </div>

        <div className="flex-1 overflow-y-auto -mx-1 px-1 min-h-[160px]">
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
            <ul className="space-y-1" role="listbox" aria-multiselectable="true" aria-label="Estudiantes disponibles">
              {usuarios.map((u) => {
                const inscripto = yaInscriptos.has(u.id);
                const elegido = seleccionados.has(u.id);
                return (
                  <li key={u.id}>
                    <button
                      type="button"
                      role="option"
                      aria-selected={elegido}
                      disabled={inscripto || inscribiendo}
                      onClick={() => toggle(u.id)}
                      className={`w-full text-left flex items-center gap-3 px-3 py-2.5 rounded-lg border transition-colors
                        disabled:opacity-50 disabled:cursor-not-allowed
                        ${elegido
                          ? 'border-surface-400 bg-surface-100'
                          : 'border-outline-variant hover:border-surface-400 hover:bg-surface-container-low'}`}
                    >
                      {/* Casilla de selección (indicador claro, sin depender de color) */}
                      <span
                        className={`w-5 h-5 rounded-md border flex items-center justify-center shrink-0 transition-colors
                          ${elegido ? 'bg-success-600 border-success-600' : 'bg-white border-surface-400'}`}
                        aria-hidden
                      >
                        {elegido && <Icon name="check" className="text-[14px] text-white" fill />}
                      </span>
                      <div className="w-8 h-8 rounded-full bg-secondary-container text-on-secondary flex items-center justify-center font-semibold text-[13px] shrink-0">
                        {nombreUsuario(u).charAt(0).toUpperCase()}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-[13px] font-medium text-on-surface truncate">{nombreUsuario(u)}</p>
                        <p className="text-[11px] text-on-surface-variant truncate">
                          {u.email}
                          <span className="font-mono"> · {u.username}</span>
                        </p>
                      </div>
                      {inscripto && (
                        <span className="text-[11px] text-on-surface-variant shrink-0">Ya inscripto</span>
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* Paginación (server-side): la selección persiste entre páginas. */}
        {total > PAGE_SIZE && (
          <div className="flex items-center justify-between gap-sm text-[12px] text-on-surface-variant">
            <span className="tabular-nums">Página {paginaActual} de {totalPaginas} · {total} estudiantes</span>
            <div className="flex items-center gap-1.5">
              <Button
                variant="ghost"
                size="sm"
                disabled={offset === 0 || cargando || inscribiendo}
                onClick={() => irAPagina(Math.max(0, offset - PAGE_SIZE))}
              >
                Anterior
              </Button>
              <Button
                variant="ghost"
                size="sm"
                disabled={offset + PAGE_SIZE >= total || cargando || inscribiendo}
                onClick={() => irAPagina(offset + PAGE_SIZE)}
              >
                Siguiente
              </Button>
            </div>
          </div>
        )}

        <div className="flex items-center justify-between gap-sm pt-base border-t border-outline-variant/40">
          <span className="text-[13px] text-on-surface-variant">
            {cantSel > 0
              ? <><strong className="text-on-surface tabular-nums">{cantSel}</strong> seleccionado{cantSel === 1 ? '' : 's'}</>
              : 'Ninguno seleccionado'}
          </span>
          <div className="flex items-center gap-sm">
            <Button variant="ghost" size="sm" onClick={onCancelar} disabled={inscribiendo}>
              Cancelar
            </Button>
            <Button
              variant="primary"
              size="sm"
              disabled={cantSel === 0 || inscribiendo}
              onClick={() => onConfirmar([...seleccionados])}
            >
              {inscribiendo ? (
                <span className="inline-flex items-center gap-xs">
                  <Icon name="progress_activity" className="ae-spin text-[18px]" />
                  Inscribiendo…
                </span>
              ) : cantSel > 1 ? `Inscribir ${cantSel}` : 'Inscribir'}
            </Button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
