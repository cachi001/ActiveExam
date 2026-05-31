import { RouterProvider, Routes } from './lib/router';
import { ScreenNavigator } from './ui/ScreenNavigator';
import Login from './screens/Login';
import EquipmentCheck from './screens/EquipmentCheck';
import Consent from './screens/Consent';
import Biometria from './screens/Biometria';
import SalaEspera from './screens/SalaEspera';
import Examen from './screens/Examen';
import Cierre from './screens/Cierre';
import Proctor from './screens/Proctor';
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
// C-26: AcuseExamen es un paso inline (no tiene ruta directa; requiere examenId como prop).
// Se embebe desde AlumnoMaterias (inscripción) y AlumnoMisExamenes (completar acuse).

export default function App() {
  const routes = {
    '/': <Login />,
    '/login': <Login />,
    '/requisitos': <EquipmentCheck />,
    '/consentimiento': <Consent />,
    '/biometria': <Biometria />,
    '/sala-espera': <SalaEspera />,
    '/examen': <Examen />,
    '/cierre': <Cierre />,
    '/proctor': <Proctor />,
    '/revisor': <Revisor />,
    '/revisor/detalle': <SessionDetail />,
    '/admin': <AdminDashboard />,
    '/admin/examenes': <ExamList />,
    '/admin/configurar': <ConfigureExam />,
    '/admin/reportes': <Reports />,
    '/admin/auditoria': <AuditPrivacy />,
    // Portal del alumno — C-21
    '/alumno/dashboard': <AlumnoDashboard />,
    '/alumno/materias': <AlumnoMaterias />,
    '/alumno/mis-examenes': <AlumnoMisExamenes />,
    '/alumno/perfil': <StudentProfile />,
    // C-23: Harness diagnóstico de detección para roles admin_examenes | coordinador
    '/admin/detection-test': <AdminDetectionHarness />,
  };

  return (
    <RouterProvider>
      <Routes routes={routes} fallback={<Login />} />
      <ScreenNavigator />
    </RouterProvider>
  );
}
