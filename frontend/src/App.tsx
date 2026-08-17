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
const UsuarioCreate         = lazy(() => import('./screens/admin/UsuarioCreate'));
const UsuarioEdit           = lazy(() => import('./screens/admin/UsuarioEdit'));
const MateriasComisiones    = lazy(() => import('./screens/MateriasComisiones'));
const DetalleUsuario        = lazy(() => import('./screens/DetalleUsuario'));
const ExamDetail            = lazy(() => import('./screens/ExamDetail'));
const ExamResultados        = lazy(() => import('./screens/ExamResultados'));
const MoodleImportPage      = lazy(() => import('./admin/ExamImport/MoodleImportPage'));
const Configuracion         = lazy(() => import('./screens/Configuracion'));
const LtiLanding            = lazy(() => import('./screens/LtiLanding'));
const BancoPreguntasPage    = lazy(() => import('./screens/BancoPreguntasPage'));
const Perfil                = lazy(() => import('./screens/Perfil'));

// Roles por área. DEBE espejar ui/nav.ts (si un item se ve en el menú y la ruta
// lo rechaza, o al reves, el usuario come un "Sin permisos" desde su propio menu)
// y CAPABILITY_ROLES del backend (si la ruta deja pasar y el endpoint responde
// 403, la accion falla en silencio).
const ESTUDIANTE: Rol[] = ['estudiante'];
// c-76: los roles 'proctor' y 'revisor' fueron ELIMINADOS del dominio.
//
// SUPERVISION_VIVO = capacidad `supervisar_vivo` ({TUTOR, COORDINADOR,
// ADMIN_SISTEMA} en el backend, D2): supervisión en vivo + registro histórico.
// El TUTOR queda ACOTADO a su comisión (scoping por comisión aplicado por el
// backend); el detalle de sesión ya oculta el botón de veredicto para quien
// no tiene `revisar_sesion` (ver DecisionRevisorForm.tsx, D3), así que abrir
// esta ruta al tutor es seguro — entra en modo lectura de decisión.
//
// COLA_REVISION = capacidad `revisar_sesion` ({COORDINADOR, ADMIN_SISTEMA}):
// el veredicto (aprobar/anular). El TUTOR NUNCA lo emite (D3, regla dura #5) —
// por eso esta cola queda con un array de roles MÁS CHICO que SUPERVISION_VIVO,
// a propósito (antes ambas compartían el mismo array `SUPERVISION`, lo que
// hubiera exigido elegir entre bloquear al tutor de supervisión en vivo o
// dejarlo entrar a la cola de decisión).
const SUPERVISION_VIVO: Rol[] = ['tutor', 'coordinador', 'admin_sistema'];
const COLA_REVISION: Rol[] = ['coordinador', 'admin_sistema'];
// Area del tutor: examenes, materias, comisiones y notas. Sin supervision,
// sin auditoria, sin configuracion.
// c-76-2: 'admin_examenes' fue ELIMINADO del dominio (solo existe un rol "Admin").
const ACADEMICO: Rol[] = ['tutor', 'coordinador', 'admin_sistema'];
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
    // Aterrizaje del launch LTI: adopta los tokens del redirect y va al dashboard.
    '/lti-login': <LtiLanding />,

    // Flujo de examen del estudiante
    '/requisitos': g(<EquipmentCheck />, ESTUDIANTE),
    '/biometria': g(<Biometria />, ESTUDIANTE),
    '/sala-espera': g(<SalaEspera />, ESTUDIANTE),
    '/pre-examen': g(<PreExamen />, ESTUDIANTE),
    '/examen': g(<Examen />, ESTUDIANTE),
    '/cierre': g(<Cierre />, ESTUDIANTE),
    '/alumno/revision/:examenId': g(<ExamenRevision />, ESTUDIANTE),
    '/alumno/informe/:sessionId': g(<InformeDevolucionAlumno />, ESTUDIANTE),

    // Supervisión en vivo: tutor (acotado a su comisión) + coordinador + admin.
    '/proctor': g(<Proctor />, SUPERVISION_VIVO),
    '/proctor/examen': g(<ExamenPersonasGrid />, SUPERVISION_VIVO),

    // Cola de revisión (veredicto): SOLO coordinador + admin — el tutor nunca decide.
    '/admin/cola-revision': g(<Revisor />, COLA_REVISION),
    '/admin/cola-revision/detalle': g(<SessionDetail />, COLA_REVISION),
    '/admin': g(<AdminDashboard />, ACADEMICO),
    '/admin/estadisticas': g(<EstadisticasInstitucionales />, ACADEMICO),
    '/admin/auditoria': g(<Auditoria />, ADMIN),
    '/admin/examenes': g(<ExamList />, ACADEMICO),
    '/admin/examenes/importar': g(<MoodleImportPage />, ACADEMICO),
    '/admin/examenes/:id/resultados': g(<ExamResultados />, ACADEMICO),
    '/admin/examenes/:id': g(<ExamDetail />, ACADEMICO),
    '/admin/detection-test': g(<AdminDetectionHarness />, ADMIN),
    '/admin/proctoring-sessions': g(<ProctoringRevisor />, SUPERVISION_VIVO),
    '/admin/proctoring-session-detail/:id': g(<ProctoringSessionDetail />, SUPERVISION_VIVO),
    '/admin/usuarios': g(<GestionUsuarios />, ADMIN),
    '/admin/usuarios/nuevo': g(<UsuarioCreate />, ADMIN),
    '/admin/materias': g(<MateriasComisiones />, ACADEMICO),
    '/admin/usuarios/:id/editar': g(<UsuarioEdit />, ADMIN),
    '/admin/usuarios/:id': g(<DetalleUsuario />, ADMIN),
    // C-73 §10.8: deja de ser admin-only. El docente entra pero SOLO ve la pestaña
    // del campus (su cuenta personal); las secciones que definen cómo se detecta el
    // fraude siguen siendo de admin_sistema — el gating fino vive en la pantalla.
    '/admin/banco-preguntas': g(<BancoPreguntasPage />, ACADEMICO),
    '/admin/configuracion': g(<Configuracion />, ADMIN),
    '/admin/perfil': g(<Perfil />, ACADEMICO),

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
