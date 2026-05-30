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
  };

  return (
    <RouterProvider>
      <Routes routes={routes} fallback={<Login />} />
      <ScreenNavigator />
    </RouterProvider>
  );
}
