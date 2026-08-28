/**
 * El resultado de una nota, con la etiqueta y el color que define el BACKEND.
 *
 * Existe para que TODAS las pantallas digan lo mismo. Antes cada una escribía
 * `aprobado ? 'Aprobado' : 'Desaprobado'` con sus propios colores: la tabla del
 * docente podía decir "En revisión" o "Anulada" sobre una nota y la tarjeta del
 * alumno seguía diciendo "Aprobado" sobre la misma.
 */
import { Badge } from './components';
import { useResultados } from '../screens/exam-detail/useCatalogosNota';

export function ResultadoNotaChip({
  resultado,
  className = '',
}: {
  /** El valor que manda el backend (`ResultadoNota`). Vacío = nada que mostrar. */
  resultado: string | null | undefined;
  className?: string;
}) {
  const catalogo = useResultados();
  if (!resultado) return null;
  const info = catalogo.get(resultado);
  return (
    <Badge tone={info?.tono ?? 'neutral'} className={className}>
      {info?.etiqueta ?? resultado}
    </Badge>
  );
}

export default ResultadoNotaChip;
