import type React from 'react';
import { Icon, Card, SectionTitle, Button } from '../../../ui/components';
import { INPUT_CLASS, LABEL_CLASS, type FormMateria } from './materiasComisionesTypes';

interface MateriaFormPanelProps {
  form: FormMateria;
  setForm: React.Dispatch<React.SetStateAction<FormMateria | null>>;
  enviando: boolean;
  error: string | null;
  primerInputRef: React.RefObject<HTMLInputElement>;
  onSubmit: (e: React.FormEvent) => void;
  onCancelar: () => void;
}

export function MateriaFormPanel({
  form,
  setForm,
  enviando,
  error,
  primerInputRef,
  onSubmit,
  onCancelar,
}: MateriaFormPanelProps) {
  return (
    <Card>
      <SectionTitle>
        {form.modo === 'crear' ? 'Nueva materia' : 'Editar materia'}
      </SectionTitle>
      <form onSubmit={onSubmit} className="space-y-md mt-md">
        <div className="grid sm:grid-cols-2 gap-md">
          {/* Código: editable tanto al crear como al editar. Es único (no la
              identidad de la fila): un duplicado lo rechaza el backend (409). */}
          <div>
            <label htmlFor="materia-codigo" className={LABEL_CLASS}>
              Código <span aria-hidden="true">*</span>
            </label>
            <input
              ref={primerInputRef}
              id="materia-codigo"
              name="materia-codigo"
              type="text"
              required
              disabled={enviando}
              placeholder="Ej. CB101"
              value={form.codigo}
              onChange={(e) =>
                setForm((prev) => prev ? { ...prev, codigo: e.target.value } : prev)
              }
              className={INPUT_CLASS}
            />
          </div>
          <div>
            <label htmlFor="materia-nombre" className={LABEL_CLASS}>
              Nombre <span aria-hidden="true">*</span>
            </label>
            <input
              id="materia-nombre"
              name="materia-nombre"
              type="text"
              required
              disabled={enviando}
              placeholder="Ej. Análisis Matemático I"
              value={form.nombre}
              onChange={(e) =>
                setForm((prev) => prev ? { ...prev, nombre: e.target.value } : prev)
              }
              className={INPUT_CLASS}
            />
          </div>
        </div>

        {error && (
          <div
            role="alert"
            className="flex items-center gap-xs text-error text-body-sm p-sm rounded-lg bg-error-container"
          >
            <Icon name="error" className="text-[18px] shrink-0" fill />
            {error}
          </div>
        )}

        <div className="flex gap-sm justify-end">
          <Button type="button" variant="ghost" onClick={onCancelar} disabled={enviando}>
            Cancelar
          </Button>
          <Button type="submit" disabled={enviando}>
            {enviando ? (
              <span className="inline-flex items-center gap-xs">
                <Icon name="progress_activity" className="ae-spin text-[20px]" />
                Guardando…
              </span>
            ) : form.modo === 'crear' ? 'Crear materia' : 'Guardar cambios'}
          </Button>
        </div>
      </form>
    </Card>
  );
}
