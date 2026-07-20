import { lazy, Suspense, type ReactNode } from 'react';
import { RouterProvider, Routes } from './lib/router';
import { ToastProvider, Toaster } from './ui/toast';
import { RequireAuth } from './lib/auth/RequireAuth';
import type { Rol } from './lib/types';
import { LoadingSpinner } from './ui/components';

const Login                 = lazy(() => import('./screens/Login'));
const EquipmentCheck        = lazy(() => import('./screens/EquipmentCheck'));
const Biometria             = lazy(() => import('./screens/Biometria'));
const SalaEspera            = lazy(() => import('./screens/SalaEspera'));
const PreExamen             = lazy(() => import('./screens/PreExamen'));
const Examen                = lazy(() => import('./screens/Examen'));
const Cierre                = lazy(() => import('./screens/Cierre'));
const ExamenRevision        = lazy(() => import('./screens/ExamenRevision'));
const InformeDevolucionAlumno = lazy(() => import('./screens/InformeDevolucionAlumno'));
const Proctor               = lazy(() => import('./screens/Proctor'));
const ExamenPersonasGrid    = lazy(() => import('./screens/ExamenPersonasGrid'));
const Revisor               = lazy(() => import('./screens/Revisor'));
const SessionDetail         = lazy(() => import('./screens/SessionDetail'));
const AdminDashboard        = lazy(() => import('./screens/AdminDashboard'));
const EstadisticasInstitucionales = lazy(() => import('./screens/EstadisticasInstitucionales'));
const Auditoria             = lazy(() => import('./screens/Auditoria'));
const ExamList              = lazy(() => import('./screens/ExamList'));
const AlumnoDashboard       = lazy(() => import('./screens/AlumnoDashboard'));
const AlumnoMaterias        = lazy(() => import('./screens/AlumnoMaterias'));
const AlumnoMisExamenes     = lazy(() => import('./screens/AlumnoMisExamenes'));
const StudentProfile        = lazy(() => import('./screens/StudentProfile'));
const AdminDetectionHarness = lazy(() => import('./screens/AdminDetectionHarness'));
const ProctoringRevisor     = lazy(() => import('./screens/ProctoringRevisor'));
const ProctoringSessionDetail = lazy(() => import('./screens/ProctoringSessionDetail'));
const GestionUsuarios       = lazy(() => import('./screens/GestionUsuarios'));
const MateriasComisiones    = lazy(() => import('./screens/MateriasComisiones'));
const DetalleUsuario        = lazy(() => import('./screens/DetalleUsuario'));
const ExamDetail            = lazy(() => import('./screens/ExamDetail'));
const ExamResultados        = lazy(() => import('./screens/ExamResultados'));
const MoodleImportPage      = lazy(() => import('./admin/ExamImport/MoodleImportPage'));
const Configuracion         = lazy(() => import('./screens/Configuracion'));
const Registro              = lazy(() => import('./screens/Registro'));

// Roles por área (modelo MVP: estudiante, proctor, admin_sistema).
const ESTUDIANTE: Rol[] = ['estudiante'];
const SUPERVISION: Rol[] = ['proctor', 'admin_sistema'];
const ADMIN: Rol[] = ['admin_sistema'];

/** Envuelve una pantalla en el guard de auth/rol. */
function g(node: ReactNode, roles: Rol[]): ReactNode {
  return <RequireAuth roles={roles}>{node}</RequireAuth>;
}

const PageFallback = () => (
  <div className="flex items-center justify-center min-h-screen">
    <LoadingSpinner size="md" label="Cargando…" />
  </div>
);

export default function App() {
  const routes = {
    // Públicas
    '/': <Login />,
    '/login': <Login />,
    '/registro': <Registro />,

    // Flujo de examen del estudiante
    '/requisitos': g(<EquipmentCheck />, ESTUDIANTE),
    '/biometria': g(<Biometria />, ESTUDIANTE),
    '/sala-espera': g(<SalaEspera />, ESTUDIANTE),
    '/pre-examen': g(<PreExamen />, ESTUDIANTE),
    '/examen': g(<Examen />, ESTUDIANTE),
    '/cierre': g(<Cierre />, ESTUDIANTE),
    '/alumno/revision/:examenId': g(<ExamenRevision />, ESTUDIANTE),
    '/alumno/informe/:sessionId': g(<InformeDevolucionAlumno />, ESTUDIANTE),

    // Supervisión en vivo (proctor + admin)
    '/proctor': g(<Proctor />, SUPERVISION),
    '/proctor/examen': g(<ExamenPersonasGrid />, SUPERVISION),

    // Revisión académica + administración
    '/revisor': g(<Revisor />, SUPERVISION),
    '/revisor/detalle': g(<SessionDetail />, SUPERVISION),
    '/admin': g(<AdminDashboard />, ADMIN),
    '/admin/estadisticas': g(<EstadisticasInstitucionales />, ADMIN),
    '/admin/auditoria': g(<Auditoria />, ADMIN),
    '/admin/examenes': g(<ExamList />, ADMIN),
    '/admin/examenes/importar': g(<MoodleImportPage />, ADMIN),
    '/admin/examenes/:id/resultados': g(<ExamResultados />, ADMIN),
    '/admin/examenes/:id': g(<ExamDetail />, ADMIN),
    '/admin/detection-test': g(<AdminDetectionHarness />, ADMIN),
    '/admin/proctoring-sessions': g(<ProctoringRevisor />, ADMIN),
    '/admin/proctoring-session-detail': g(<ProctoringSessionDetail />, SUPERVISION),
    '/admin/usuarios': g(<GestionUsuarios />, ADMIN),
    '/admin/materias': g(<MateriasComisiones />, ADMIN),
    '/admin/usuarios/:id': g(<DetalleUsuario />, ADMIN),
    '/admin/configuracion': g(<Configuracion />, ADMIN),

    // Portal del alumno — C-21
    '/alumno': g(<AlumnoDashboard />, ESTUDIANTE),
    '/alumno/dashboard': g(<AlumnoDashboard />, ESTUDIANTE),
    '/alumno/materias': g(<AlumnoMaterias />, ESTUDIANTE),
    '/alumno/mis-examenes': g(<AlumnoMisExamenes />, ESTUDIANTE),
    '/alumno/perfil': g(<StudentProfile />, ESTUDIANTE),
  };

  return (
    <ToastProvider>
      <RouterProvider>
        <Suspense fallback={<PageFallback />}>
          <Routes routes={routes} fallback={<Login />} />
        </Suspense>
      </RouterProvider>
      <Toaster />
    </ToastProvider>
  );
}
