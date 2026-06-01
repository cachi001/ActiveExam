// Navegador flotante de pantallas — herramienta para la demo/presentación:
// permite saltar a cualquiera de las pantallas del MVP, agrupadas por rol.
import { useState } from 'react';
import { Icon } from './components';
import { useRouter } from '../lib/router';
import { useApp } from '../lib/store';
import { api, PRINCIPALES } from '../lib/api';
import type { Rol } from '../lib/types';

interface Item { to: string; label: string; rol?: Rol; }
interface Group { titulo: string; icon: string; items: Item[] }

const GRUPOS: Group[] = [
  {
    titulo: 'Estudiante', icon: 'school', items: [
      { to: '/login', label: 'Ingreso', rol: 'estudiante' },
      // Portal del alumno — C-21
      { to: '/alumno/dashboard', label: 'Dashboard del alumno' },
      { to: '/alumno/materias', label: 'Materias e inscripción' },
      { to: '/alumno/mis-examenes', label: 'Mis exámenes' },
      { to: '/alumno/perfil', label: 'Perfil del alumno' },
      // Flujo de examen
      { to: '/requisitos', label: 'Chequeo de requisitos' },
      { to: '/consentimiento', label: 'Consentimiento informado' },
      { to: '/biometria', label: 'Verificación biométrica' },
      { to: '/sala-espera', label: 'Sala de espera' },
      { to: '/examen', label: 'Examen en curso' },
      { to: '/cierre', label: 'Cierre de examen' },
    ],
  },
  {
    titulo: 'Proctor (en vivo)', icon: 'visibility', items: [
      { to: '/proctor', label: 'Supervisión en vivo', rol: 'proctor' },
    ],
  },
  {
    titulo: 'Revisión académica', icon: 'gavel', items: [
      { to: '/revisor', label: 'Cola de revisión', rol: 'revisor' },
      { to: '/revisor/detalle', label: 'Detalle de sesión' },
    ],
  },
  {
    titulo: 'Administración', icon: 'admin_panel_settings', items: [
      { to: '/admin', label: 'Dashboard', rol: 'admin_examenes' },
      { to: '/admin/examenes', label: 'Listado de exámenes' },
      { to: '/admin/configurar', label: 'Configurar examen' },
      { to: '/admin/reportes', label: 'Reportes y analítica' },
      { to: '/admin/auditoria', label: 'Auditoría y privacidad' },
      { to: '/admin/detection-test', label: 'Test de detección', rol: 'admin_examenes' },
    ],
  },
];

export function ScreenNavigator() {
  const [open, setOpen] = useState(false);
  const { path, navigate } = useRouter();
  const setPrincipal = useApp((s) => s.setPrincipal);

  const go = async (item: Item) => {
    if (item.rol) setPrincipal(PRINCIPALES[item.rol], item.rol);
    navigate(item.to);
    setOpen(false);
  };

  return (
    <>
      <button
        onClick={() => setOpen((v) => !v)}
        className="fixed bottom-5 right-5 z-[100] w-12 h-12 rounded-full bg-primary text-on-primary shadow-card-lg flex items-center justify-center hover:bg-primary-container transition-colors"
        title="Navegador de pantallas (demo)"
      >
        <Icon name={open ? 'close' : 'apps'} />
      </button>

      {open && (
        <div className="fixed bottom-20 right-5 z-[100] w-80 max-h-[70vh] overflow-y-auto rounded-xl bg-surface-container-lowest border border-outline-variant/60 shadow-card-lg p-md animate-in fade-in slide-in-from-bottom-4">
          <div className="flex items-center justify-between mb-sm px-base">
            <span className="font-headline text-title-lg text-on-surface">Pantallas</span>
            <span className="text-label-sm text-on-surface-variant">{api.modoDemo ? 'Modo demo' : 'Backend real'}</span>
          </div>
          {GRUPOS.map((g) => (
            <div key={g.titulo} className="mb-sm">
              <div className="flex items-center gap-base px-base py-base text-label-sm uppercase tracking-wide text-on-surface-variant">
                <Icon name={g.icon} className="text-[16px]" /> {g.titulo}
              </div>
              <div className="space-y-base">
                {g.items.map((it) => (
                  <button key={it.to} onClick={() => go(it)}
                    className={`w-full text-left px-sm py-base rounded-lg text-label-md transition-colors ${
                      path === it.to ? 'bg-primary-fixed text-on-primary-fixed-variant font-semibold' : 'text-on-surface hover:bg-surface-container'
                    }`}>
                    {it.label}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
