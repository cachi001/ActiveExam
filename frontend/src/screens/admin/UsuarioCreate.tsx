/**
 * UsuarioCreate — Página dedicada de alta de usuario.
 *
 * Ruta: /admin/usuarios/nuevo
 * Protegida por capacidad `gestionar_usuarios` (solo admin_sistema).
 *
 * Flujo:
 *  1. Formulario de alta (legajo, email, nombre, apellido, password opcional, roles).
 *  2. Invoca POST /users sin cambiar contrato; captura `password_generada`.
 *  3. Si hay `password_generada` → modal con clave temporal + botón copiar.
 *  4. "Entendido" navega a /admin/usuarios.
 *
 * c-76 — tarea 1.1–1.3
 */

import { useState } from 'react';
import { StaffShell } from '../../ui/shells';
import { Button, Card, SectionTitle, Icon } from '../../ui/components';
import { HelpButton } from '../../ui/HelpButton';
import { STAFF_NAV } from '../../ui/nav';
import { useToast } from '../../ui/toast';
import { useNavigate, Link } from '../../lib/router';
import { useAuth } from '../../lib/authStore';
import { api } from '../../lib/api';
import { tieneCapacidad } from '../../lib/capabilities';
import {
  FORM_VACIO,
  type FormState,
} from './components/UsuarioHelpers';
import { UsuarioFormPanel } from './components/UsuarioFormPanel';

// ---------------------------------------------------------------------------
// Modal de clave temporal
// ---------------------------------------------------------------------------

interface ModalClaveProps {
  clave: string;
  email: string;
  onCerrar: () => void;
}

function ModalClaveTemporal({ clave, email, onCerrar }: ModalClaveProps) {
  const [copiado, setCopiado] = useState(false);

  async function copiar() {
    try {
      await navigator.clipboard.writeText(clave);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 2000);
    } catch {
      // El navegador puede rechazar clipboard en contextos sin foco
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-clave-titulo"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-md"
    >
      <div className="bg-white rounded-lg shadow-2xl w-full max-w-md p-lg space-y-md">
        {/* Encabezado */}
        <div className="flex items-start gap-sm">
          <div className="w-10 h-10 rounded-full bg-success-50 flex items-center justify-center shrink-0">
            <Icon name="check_circle" className="text-[22px] text-success-600" fill />
          </div>
          <div>
            <h2 id="modal-clave-titulo" className="font-headline text-title-md text-on-surface">
              Usuario creado
            </h2>
            <p className="text-body-sm text-on-surface-variant mt-base">
              Compartí esta contraseña temporal con{' '}
              <span className="font-medium text-on-surface">{email}</span>.{' '}
              El usuario deberá cambiarla en su primer ingreso.
            </p>
          </div>
        </div>

        {/* Bloque de clave */}
        <div className="bg-surface-50 rounded-lg border border-surface-200 p-md">
          <p className="text-label-sm text-on-surface-variant mb-sm uppercase tracking-wide">
            Contraseña temporal
          </p>
          <div className="flex items-center gap-sm">
            <code className="flex-1 font-mono text-body-lg font-bold text-on-surface tracking-widest select-all">
              {clave}
            </code>
            <button
              type="button"
              onClick={copiar}
              aria-label="Copiar contraseña"
              title="Copiar contraseña"
              className="shrink-0 p-sm rounded-md hover:bg-surface-100 text-on-surface-variant hover:text-primary transition-colors"
            >
              {copiado ? (
                <Icon name="check" className="text-[20px] text-success-600" />
              ) : (
                <Icon name="content_copy" className="text-[20px]" />
              )}
            </button>
          </div>
        </div>

        {/* Aviso ámbar */}
        <div className="flex items-start gap-sm rounded-lg bg-warning-50 border border-warning-200 px-md py-sm">
          <Icon name="warning" className="text-[18px] text-warning-600 shrink-0 mt-0.5" fill />
          <p className="text-body-sm text-warning-800">
            Guardala ahora — no la vas a volver a ver una vez que cierres esta ventana.
          </p>
        </div>

        {/* Acción */}
        <Button className="w-full" onClick={onCerrar}>
          Entendido, ir a usuarios
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Panel informativo lateral
// ---------------------------------------------------------------------------

function PanelInfoContrasena() {
  return (
    <Card>
      <div className="flex items-center gap-sm pb-md border-b border-surface-100 mb-md">
        <div className="w-8 h-8 rounded-full bg-warning-50 flex items-center justify-center shrink-0">
          <Icon name="key" className="text-[18px] text-warning-600" />
        </div>
        <h3 className="font-headline text-title-sm text-on-surface">Contraseña automática</h3>
      </div>
      <p className="text-body-sm text-on-surface-variant leading-relaxed">
        Si no ingresás una contraseña, el sistema genera una temporal segura al crear el
        usuario. Se mostrará una sola vez — copiala y compartila con el usuario.
        Deberá cambiarla en su primer ingreso a la plataforma.
      </p>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Componente principal
// ---------------------------------------------------------------------------

export default function UsuarioCreate() {
  const toast = useToast();
  const navigate = useNavigate();
  const principal = useAuth((s) => s.principal);

  const [form, setForm] = useState<FormState>(FORM_VACIO);
  const [formError, setFormError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [claveTemporal, setClaveTemporal] = useState<{ clave: string; email: string } | null>(null);

  // Guard de capacidad: el componente se monta en /admin/usuarios/nuevo protegido
  // por ADMIN en App.tsx, pero por correctitud verificamos la capacidad aquí también
  // para que el test de acceso denegado funcione sin RequireAuth.
  const puedeGestionar =
    principal != null && tieneCapacidad(principal.roles as Parameters<typeof tieneCapacidad>[0], 'gestionar_usuarios');

  if (!puedeGestionar) {
    return (
      <StaffShell
        nav={STAFF_NAV}
        title="Nuevo usuario"
        subtitle="Alta de usuario en la plataforma."
      >
        <Card>
          <div className="flex flex-col items-center gap-md py-xl text-center">
            <div className="w-14 h-14 rounded-2xl bg-error-container text-error flex items-center justify-center">
              <Icon name="block" className="text-[28px]" fill />
            </div>
            <div>
              <p className="font-headline text-title-md text-on-surface">Sin permiso</p>
              <p className="text-body-md text-on-surface-variant mt-base">
                No tenés permiso para gestionar usuarios.
              </p>
            </div>
            <Button variant="outline" icon="arrow_back" onClick={() => navigate('/admin/usuarios')}>
              Volver a usuarios
            </Button>
          </div>
        </Card>
      </StaffShell>
    );
  }

  function cambiarTexto(campo: keyof Omit<FormState, 'roles'>) {
    return (e: React.ChangeEvent<HTMLInputElement>) =>
      setForm((prev) => ({ ...prev, [campo]: e.target.value }));
  }

  function toggleRol(rol: string) {
    setForm((prev) => {
      const existe = prev.roles.includes(rol);
      return {
        ...prev,
        roles: existe ? prev.roles.filter((r) => r !== rol) : [...prev.roles, rol],
      };
    });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);

    const roles = form.roles;
    if (roles.length === 0) {
      setFormError('Seleccioná al menos un rol.');
      return;
    }
    if (form.password && form.password.length < 8) {
      setFormError('La contraseña debe tener al menos 8 caracteres.');
      return;
    }

    setEnviando(true);
    try {
      const resp = await api.crearUsuario({
        id_institucional: form.id_institucional,
        email: form.email,
        password: form.password || undefined,
        roles,
        nombre: form.nombre || undefined,
        apellido: form.apellido || undefined,
      });

      if (resp.password_generada) {
        // Mostramos el modal; la navegación ocurre al cerrarlo
        setClaveTemporal({ clave: resp.password_generada, email: resp.email });
      } else {
        toast.success('Usuario creado correctamente.');
        navigate('/admin/usuarios');
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes('409')) {
        setFormError('Ya existe un usuario con ese email o legajo.');
      } else {
        setFormError(`Error al crear: ${msg}`);
      }
    } finally {
      setEnviando(false);
    }
  }

  function cerrarModal() {
    setClaveTemporal(null);
    navigate('/admin/usuarios');
  }

  return (
    <StaffShell
      nav={STAFF_NAV}
      title="Nuevo usuario"
      subtitle="Alta de usuario en la plataforma."
      help={
        <HelpButton title="Nuevo usuario">
          <p>Completá el formulario para dar de alta un usuario. Si no ingresás contraseña, el sistema genera una temporal y te la muestra al crear.</p>
          <p>El usuario deberá cambiar la contraseña en su primer ingreso.</p>
        </HelpButton>
      }
      actions={
        <Link to="/admin/usuarios">
          <Button variant="outline" icon="arrow_back" size="sm">
            Volver a usuarios
          </Button>
        </Link>
      }
    >
      {/* Modal de clave temporal — aparece sobre todo */}
      {claveTemporal && (
        <ModalClaveTemporal
          clave={claveTemporal.clave}
          email={claveTemporal.email}
          onCerrar={cerrarModal}
        />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-lg animate-in fade-in duration-500">
        {/* Formulario ocupa 2/3 */}
        <div className="lg:col-span-2">
          <UsuarioFormPanel
            modoForm="crear"
            editando={null}
            form={form}
            formError={formError}
            enviando={enviando}
            cambiarTexto={cambiarTexto}
            toggleRol={toggleRol}
            onSubmit={handleSubmit}
            onCancelar={() => navigate('/admin/usuarios')}
          />
        </div>

        {/* Panel informativo ocupa 1/3 */}
        <div>
          <PanelInfoContrasena />
        </div>
      </div>
    </StaffShell>
  );
}
