import { useState, useEffect, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Icon, Button } from '../../../ui/components';
import { api } from '../../../lib/api';
import type { UsuarioAdmin } from '../../../lib/types';

const INPUT_CLASS =
  'w-full rounded-md border border-outline-variant bg-surface px-3 py-2.5 text-sm ' +
  'text-on-surface outline-none transition-colors hover:border-outline focus:border-primary ' +
  'focus:ring-1 focus:ring-primary/30 disabled:opacity-50 disabled:cursor-not-allowed';

function nombreUsuario(u: UsuarioAdmin): string {
  const completo = [u.nombre, u.apellido].filter(Boolean).join(' ').trim();
  return completo || u.id_institucional || u.email;
}

export interface AlumnoPickerModalProps {
  abierto: boolean;
  comisionNombre: string;
  yaInscriptos: Set<string>;
  inscribiendo: boolean;
  onConfirmar: (usuarioId: string) => void;
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

  useEffect(() => {
    if (!abierto) return;
    setQInput('');
    setSeleccionado(null);
    void cargar('');
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
