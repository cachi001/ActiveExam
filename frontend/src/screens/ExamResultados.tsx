/**
 * ExamResultados — Página dedicada a los alumnos que rindieron un examen (C-72 §19).
 *
 * Ruta: /admin/examenes/:id/resultados. Antes esta tabla colgaba al final del
 * detalle del examen; ahora tiene su propia pantalla. El contenido (filtros,
 * tabla, paginación, sync a Moodle) vive en `ResultadosExamenPanel`, compartido
 * con el picker de `/admin/notas` — acá solo se resuelve el título desde la
 * ruta y se agrega el botón "Volver". Se llega acá por deep-link directo
 * (click en una fila/acción de `ExamList.tsx`, o un link de `Auditoria.tsx`
 * hacia el examen puntual) — `Notas.tsx` no reemplaza esto porque su picker
 * no acepta un examen preseleccionado por URL.
 */
import { useEffect, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Button } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { STAFF_NAV } from '../ui/nav';
import { useRouteParam } from '../lib/router';
import { API_BASE } from '../lib/api';
import { authProvider } from '../lib/authProvider';
import { getExamenHeaderFn } from '../lib/examContentResultados';
import type { ExamenContenidoResumen } from '../lib/types';
import { ResultadosExamenPanel } from './exam-detail/ResultadosExamenPanel';

export default function ExamResultados() {
  const examenId = useRouteParam('id');
  const [examen, setExamen] = useState<ExamenContenidoResumen | null>(null);

  useEffect(() => {
    if (!examenId) return;
    getExamenHeaderFn(API_BASE, authProvider.getToken(), examenId)
      .then(setExamen)
      .catch(() => { /* el título cae al fallback */ });
  }, [examenId]);

  const volver = () => window.history.back();

  return (
    <StaffShell
      nav={STAFF_NAV}
      title={examen?.titulo ? `Alumnos que rindieron — ${examen.titulo}` : 'Alumnos que rindieron'}
      subtitle={
        examen
          ? [examen.materia_nombre, examen.comision_nombre].filter(Boolean).join(' · ') || 'Resultados y sincronización con Moodle.'
          : 'Resultados y sincronización con Moodle.'
      }
      help={
        <HelpButton title="Alumnos que rindieron">
          <p>
            Lista todos los intentos de este examen: nota obtenida, estado de sincronización
            con Moodle y si la nota está retenida por revisión.
          </p>
          <p>
            <strong>Publicar notas en Moodle</strong> envía las notas pendientes al campus.
            Podés publicar todas las pendientes con el botón principal, seleccionar filas
            individualmente para publicar una selección, o usar el botón por fila para
            publicar una nota de forma individual.
            Las notas retenidas por riesgo no se envían hasta que una persona lo apruebe
            desde la Cola de revisión.
          </p>
        </HelpButton>
      }
    >
      <div className="space-y-lg animate-in fade-in duration-500">
        <Button variant="ghost" icon="arrow_back" size="sm" onClick={volver}>
          Volver
        </Button>

        {examenId && <ResultadosExamenPanel examenId={examenId} />}
      </div>
    </StaffShell>
  );
}
