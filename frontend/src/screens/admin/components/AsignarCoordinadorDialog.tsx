/**
 * AsignarCoordinadorDialog — envoltorio fino sobre `AsignarResponsableDialog`.
 *
 * c-78: el diálogo se generalizó para cubrir los DOS roles de materia
 * (coordinador y profesor) sin duplicar el componente. Este archivo se conserva
 * porque es el nombre que ya usa la pantalla de Materias, y porque "coordinador"
 * dice más en el punto de uso que un genérico.
 */
import {
  AsignarResponsableDialog,
  type ResponsableInfo,
} from './AsignarResponsableDialog';

export function AsignarCoordinadorDialog({
  materiaId,
  materiaNombre,
  coordinadoresActuales,
  onCerrar,
  onCambiado,
}: {
  materiaId: string;
  materiaNombre: string;
  coordinadoresActuales: ResponsableInfo[];
  onCerrar: () => void;
  onCambiado: (coordinadores: ResponsableInfo[]) => void;
}) {
  return (
    <AsignarResponsableDialog
      rol="coordinador"
      materiaId={materiaId}
      materiaNombre={materiaNombre}
      actuales={coordinadoresActuales}
      onCerrar={onCerrar}
      onCambiado={onCambiado}
    />
  );
}

/** Gemelo para el rol PROFESOR (c-78 E-04). */
export function AsignarProfesorDialog({
  materiaId,
  materiaNombre,
  profesoresActuales,
  onCerrar,
  onCambiado,
}: {
  materiaId: string;
  materiaNombre: string;
  profesoresActuales: ResponsableInfo[];
  onCerrar: () => void;
  onCambiado: (profesores: ResponsableInfo[]) => void;
}) {
  return (
    <AsignarResponsableDialog
      rol="profesor"
      materiaId={materiaId}
      materiaNombre={materiaNombre}
      actuales={profesoresActuales}
      onCerrar={onCerrar}
      onCambiado={onCambiado}
    />
  );
}
