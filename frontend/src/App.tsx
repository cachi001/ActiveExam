import type { ReactNode } from 'react';
import { RouterProvider, Routes } from './lib/router';
import { ScreenNavigator } from './ui/ScreenNavigator';
import { ToastProvider, Toaster } from './ui/toast';
import { DEV_TOOLS_ENABLED } from './lib/devConfig';
import { RequireAuth } from './lib/auth/RequireAuth';
import type { Rol } from './lib/types';
import Login from './screens/Login';
import EquipmentCheck from './screens/EquipmentCheck';
import Consent from './screens/Consent';
import Biometria from './screens/Biometria';
import SalaEspera from './screens/SalaEspera';
import Examen from './screens/Examen';
import Cierre from './screens/Cierre';
import Proctor from './screens/Proctor';
import ExamenPersonasGrid from './screens/ExamenPersonasGrid';
import Revisor from './screens/Revisor';
import SessionDetail from './screens/SessionDetail';
import AdminDashboard from './screens/AdminDashboard';
import ExamList from './screens/ExamList';
import ConfigureExam from './screens/ConfigureExam';
import Reports from './screens/Reports';
import AuditPrivacy from './screens/AuditPrivacy';
// Portal del alumno — C-21
import AlumnoDashboard from './screens/AlumnoDashboard';
import AlumnoMaterias from './screens/AlumnoMaterias';
import AlumnoMisExamenes from './screens/AlumnoMisExamenes';
// C-22: StudentProfile reemplaza AlumnoPerfil con el flujo real de enrollment
import StudentProfile from './screens/StudentProfile';
// C-23: Harness de diagnóstico de detección para administradores
import AdminDetectionHarness from './screens/AdminDetectionHarness';
// C-46: Revisión de sesiones del backend slim de proctoring
import ProctoringRevisor from './screens/ProctoringRevisor';
import ProctoringSessionDetail from './screens/ProctoringSessionDetail';
// C-61: Gestión de usuarios y registro público
import GestionUsuarios from './screens/GestionUsuarios';
import Registro from './screens/Registro';

// Roles por área (modelo MVP: estudiante, proctor, admin_sistema).
const ESTUDIANTE: Rol[] = ['estudiante'];
const SUPERVISION: Rol[] = ['proctor', 'admin_sistema'];
const ADMIN: Rol[] = ['admin_sistema'];

/** Envuelve una pantalla en el guard de auth/rol. */
function g(node: ReactNode, roles: Rol[]): ReactNode {
  return <RequireAuth roles={roles}>{node}</RequireAuth>;
}

export default function App() {
  const routes = {
    // Públicas
    '/': <Login />,
    '/login': <Login />,
    '/registro': <Registro />,

    // Flujo de examen del estudiante
    '/requisitos': g(<EquipmentCheck />, ESTUDIANTE),
    '/consentimiento': g(<Consent />, ESTUDIANTE),
    '/biometria': g(<Biometria />, ESTUDIANTE),
    '/sala-espera': g(<SalaEspera />, ESTUDIANTE),
    '/examen': g(<Examen />, ESTUDIANTE),
    '/cierre': g(<Cierre />, ESTUDIANTE),

    // Supervisión en vivo (proctor + admin)
    '/proctor': g(<Proctor />, SUPERVISION),
    '/proctor/examen': g(<ExamenPersonasGrid />, SUPERVISION),

    // Revisión académica + administración (admin_sistema)
    '/revisor': g(<Revisor />, ADMIN),
    '/revisor/detalle': g(<SessionDetail />, ADMIN),
    '/admin': g(<AdminDashboard />, ADMIN),
    '/admin/examenes': g(<ExamList />, ADMIN),
    '/admin/configurar': g(<ConfigureExam />, ADMIN),
    '/admin/reportes': g(<Reports />, ADMIN),
    '/admin/auditoria': g(<AuditPrivacy />, ADMIN),
    '/admin/detection-test': g(<AdminDetectionHarness />, ADMIN),
    // C-46: Revisión de sesiones del backend slim de proctoring
    '/admin/proctoring-sessions': g(<ProctoringRevisor />, ADMIN),
    '/admin/proctoring-session-detail': g(<ProctoringSessionDetail />, ADMIN),
    // C-61: Gestión de usuarios
    '/admin/usuarios': g(<GestionUsuarios />, ADMIN),

    // Portal del alumno — C-21
    '/alumno/dashboard': g(<AlumnoDashboard />, ESTUDIANTE),
    '/alumno/materias': g(<AlumnoMaterias />, ESTUDIANTE),
    '/alumno/mis-examenes': g(<AlumnoMisExamenes />, ESTUDIANTE),
    '/alumno/perfil': g(<StudentProfile />, ESTUDIANTE),
  };

  return (
    <ToastProvider>
      <RouterProvider>
        <Routes routes={routes} fallback={<Login />} />
        {DEV_TOOLS_ENABLED && <ScreenNavigator />}
      </RouterProvider>
      <Toaster />
    </ToastProvider>
  );
}
