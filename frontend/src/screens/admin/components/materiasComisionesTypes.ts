export const INPUT_CLASS =
  'w-full rounded-md border border-outline-variant bg-surface px-3 py-2.5 text-sm ' +
  'text-on-surface outline-none transition-colors hover:border-outline focus:border-primary ' +
  'focus:ring-1 focus:ring-primary/30 disabled:opacity-50 disabled:cursor-not-allowed';

export const LABEL_CLASS = 'block text-xs font-semibold text-on-surface-variant uppercase tracking-wide mb-1';

export interface FormMateria {
  modo: 'crear' | 'editar';
  id: string | null;
  codigo: string;
  nombre: string;
}

export const FORM_MATERIA_VACIO: FormMateria = { modo: 'crear', id: null, codigo: '', nombre: '' };

export interface FormComision {
  modo: 'crear' | 'editar';
  materiaId: string;
  comisionId: string | null;
  codigo: string;
  nombre: string;
  periodo: string;
  anio: string;
}

export const FORM_COMISION_VACIO: Omit<FormComision, 'materiaId'> = {
  modo: 'crear',
  comisionId: null,
  codigo: '',
  nombre: '',
  periodo: '',
  anio: '',
};

export function mensajeDeError(err: unknown, contexto: 'materia' | 'comision'): string {
  const e = err as Error & { status?: number };
  if (e.status === 409) {
    return contexto === 'materia'
      ? 'Ya existe una materia con ese código.'
      : 'Ya existe una comisión con ese código en esta materia.';
  }
  if (e.status === 422) return 'Datos inválidos. Revisá los campos e intentá de nuevo.';
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
