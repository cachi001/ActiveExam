/**
 * UsuarioEdit — Página dedicada de edición de usuario.
 *
 * Ruta: /admin/usuarios/:id/editar
 * Protegida por capacidad `gestionar_usuarios` (solo admin_sistema).
 *
 * Antes el botón "Editar" abría el formulario inline en la misma página del
 * listado (GestionUsuarios.tsx). Se movió a una página propia, consistente con
 * "Nuevo usuario" (/admin/usuarios/nuevo) y con el patrón de referencia
 * (Sistema-de-Gestion-Convenios: Usuarios → UsuarioEdit en ruta propia).
 */

import { useEffect, useState } from 'react';
import { StaffShell } from '../../ui/shells';
import { Button, Card, Icon } from '../../ui/components';
import { HelpButton } from '../../ui/HelpButton';
import { STAFF_NAV } from '../../ui/nav';
import { useToast } from '../../ui/toast';
import { useNavigate, useRouteParam, Link } from '../../lib/router';
import { useAuth } from '../../lib/authStore';
import { api } from '../../lib/api';
import { tieneCapacidad } from '../../lib/capabilities';
import { FORM_VACIO, type FormState } from './components/UsuarioHelpers';
import { hayCambios as calcularCambios } from './components/usuarioCambios';
import { ResetearPasswordCard } from './components/ResetearPasswordCard';
import { BloqueoCuentaCard } from './components/BloqueoCuentaCard';
import { UsuarioFormPanel } from './components/UsuarioFormPanel';
import type { UsuarioAdmin } from '../../lib/types';

export default function UsuarioEdit() {
  const toast = useToast();
  const navigate = useNavigate();
  const usuarioId = useRouteParam('id');
  const principal = useAuth((s) => s.principal);

  const [usuario, setUsuario] = useState<UsuarioAdmin | null>(null);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(FORM_VACIO);
  const [formError, setFormError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const puedeGestionar =
    principal != null && tieneCapacidad(principal.roles as Parameters<typeof tieneCapacidad>[0], 'gestionar_usuarios');

  // Se vuelve al LISTADO, que es de donde se entra en la práctica (el menú de cada
  // fila) y un destino que siempre existe. Antes decía "Volver al detalle" y llevaba
  // ahí siempre: si entraste por el listado, terminabas en una pantalla por la que
  // nunca pasaste, y el cartel además te decía que venías de un lugar donde no
  // habías estado.
  const volverA = '/admin/usuarios';

  useEffect(() => {
    if (!usuarioId) return;
    api.obtenerDetalleUsuario(usuarioId)
      .then((data) => {
        setUsuario(data);
        setForm({
          email: data.email,
          username: '', // no editable acá (EditarUsuarioRequest no lo acepta)
          nombre: data.nombre ?? '',
          apellido: data.apellido ?? '',
          roles: [...data.roles],
        });
      })
      .catch((err) => setErrorCarga(err instanceof Error ? err.message : String(err)))
      .finally(() => setCargando(false));
  }, [usuarioId]);

  if (!puedeGestionar) {
    return (
      <StaffShell nav={STAFF_NAV} title="Editar usuario" subtitle="Edición de usuario en la plataforma.">
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
      return { ...prev, roles: existe ? prev.roles.filter((r) => r !== rol) : [...prev.roles, rol] };
    });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    if (!usuarioId) return;
    if (form.roles.length === 0) {
      setFormError('Seleccioná al menos un rol.');
      return;
    }
    setEnviando(true);
    try {
      await api.editarUsuario(usuarioId, {
        email: form.email || undefined,
        nombre: form.nombre || undefined,
        apellido: form.apellido || undefined,
        roles: form.roles,
      });
      toast.success('Usuario actualizado correctamente.');
      navigate(volverA);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes('409')) {
        setFormError('Ya existe un usuario con ese email, o no podés quitarte el rol de administrador.');
      } else {
        setFormError(`Error al guardar: ${msg}`);
      }
    } finally {
      setEnviando(false);
    }
  }

  return (
    <StaffShell
      nav={STAFF_NAV}
      title="Editar usuario"
      subtitle={
        usuario
          ? `Estás editando a ${usuario.nombre && usuario.apellido ? `${usuario.nombre} ${usuario.apellido}` : usuario.email}.`
          : 'Modificá los datos de un usuario de la plataforma.'
      }
      help={
        <HelpButton title="Editar usuario">
          <p>Modificá el email, nombre, apellido o roles del usuario. El nombre de usuario (para loguearse) no se puede cambiar acá.</p>
        </HelpButton>
      }
      actions={
        /* A DONDE se vuelve depende de por donde entraste. Antes decia siempre
           "Volver al detalle" y llevaba ahi, aunque hubieras llegado desde el
           listado: te dejaba en una pantalla por la que nunca pasaste. */
        <Link to={volverA}>
          <Button variant="ghost" icon="arrow_back" size="sm">
            Volver a usuarios
          </Button>
        </Link>
      }
    >
      <div className="animate-in fade-in duration-500">
        {cargando ? (
          <Card>
            <div className="py-xl flex items-center justify-center text-on-surface-variant">
              <Icon name="progress_activity" className="ae-spin text-[24px]" />
            </div>
          </Card>
        ) : errorCarga || !usuario ? (
          <Card>
            <div className="flex flex-col items-center gap-md py-xl text-center">
              <p className="text-body-md text-error">No se pudo cargar el usuario.</p>
              {errorCarga && <p className="text-body-sm text-on-surface-variant">{errorCarga}</p>}
              <Button variant="outline" icon="arrow_back" onClick={() => navigate('/admin/usuarios')}>
                Volver a usuarios
              </Button>
            </div>
          </Card>
        ) : (
          <UsuarioFormPanel
            modoForm="editar"
            editando={usuario}
            form={form}
            formError={formError}
            enviando={enviando}
            cambiarTexto={cambiarTexto}
            toggleRol={toggleRol}
            onSubmit={handleSubmit}
            onCancelar={() => navigate(volverA)}
            hayCambios={calcularCambios(usuario, form)}
          />
        )}

        {/* Bloqueo por intentos fallidos: no se veia en NINGUNA pantalla, y la
            unica forma de destrabar a alguien era resetearle la contrasena. */}
        {!cargando && !errorCarga && usuario && (
          <div className="mt-lg">
            <BloqueoCuentaCard
              usuario={usuario}
              onDesbloqueado={() => {
                if (!usuarioId) return;
                api.obtenerDetalleUsuario(usuarioId).then(setUsuario).catch(() => {
                  // El desbloqueo ya se hizo; si el refresco falla, la tarjeta
                  // muestra el estado destrabado igual (lo lleva en su estado).
                });
              }}
            />
          </div>
        )}

        {/* Reseteo de contrasena: el endpoint existia desde c-78 pero NINGUNA
            pantalla lo llamaba, asi que la unica forma de destrabar a alguien que
            olvido su clave era pegarle a la API a mano. */}
        {!cargando && !errorCarga && usuario && (
          <div className="mt-lg">
            <ResetearPasswordCard usuario={usuario} />
          </div>
        )}
      </div>
    </StaffShell>
  );
}
