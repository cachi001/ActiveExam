/**
 * Registro — registro público de nuevos estudiantes (C-61).
 *
 * Ruta: /registro (PÚBLICA — sin RequireAuth)
 * Invoca api.registrarUsuario() (dual real/mock).
 *
 * Reglas:
 * - El servidor fuerza rol ["estudiante"] y auth_provider="local".
 * - El cuerpo NO incluye campo "roles" (extra='forbid' en el backend — previene auto-elevación).
 * - Validaciones cliente: email con dominio institucional (si INSTITUTION.dominioEmail no está vacío),
 *   coincidencia de contraseñas, fuerza mínima (≥8 chars).
 * - Tras registro exitoso (201): redirigir al login sin emitir token.
 * - Errores: 409 duplicado, 422 validación.
 */

import { useState } from 'react';
import { Icon, Button } from '../ui/components';
import { TextField } from '../ui/TextField';
import { Link, useNavigate } from '../lib/router';
import { api } from '../lib/api';
import { INSTITUTION } from '../config/institution';

export default function Registro() {
  const navigate = useNavigate();

  const [form, setForm] = useState({
    id_institucional: '',
    nombre: '',
    apellido: '',
    email: '',
    password: '',
    password_confirmacion: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exito, setExito] = useState(false);

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  function cambiar(campo: keyof typeof form) {
    return (e: React.ChangeEvent<HTMLInputElement>) =>
      setForm((prev) => ({ ...prev, [campo]: e.target.value }));
  }

  /**
   * Validación cliente (C-61):
   * - Email obligatorio con formato válido (el backend revalida).
   * - Las contraseñas deben coincidir y tener al menos 8 caracteres.
   * Registro ABIERTO: se acepta cualquier correo válido, sin validación de dominio.
   */
  function validar(): string | null {
    if (!form.id_institucional.trim()) return 'El legajo / ID institucional es obligatorio.';
    if (!form.nombre.trim()) return 'El nombre es obligatorio.';
    if (!form.apellido.trim()) return 'El apellido es obligatorio.';
    if (!form.email.trim()) return 'El email es obligatorio.';
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email.trim())) return 'El email no tiene un formato válido.';
    if (form.password.length < 8) return 'La contraseña debe tener al menos 8 caracteres.';
    if (form.password !== form.password_confirmacion) return 'Las contraseñas no coinciden.';

    return null;
  }

  // ---------------------------------------------------------------------------
  // Submit
  // ---------------------------------------------------------------------------

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const err = validar();
    if (err) { setError(err); return; }

    setLoading(true);
    try {
      await api.registrarUsuario({
        id_institucional: form.id_institucional,
        nombre: form.nombre,
        apellido: form.apellido,
        email: form.email,
        password: form.password,
        password_confirmacion: form.password_confirmacion,
      });
      setExito(true);
      // Redirigir al login después de 2 segundos.
      setTimeout(() => navigate('/login'), 2000);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes('409')) {
        setError('Ya existe una cuenta con ese email o legajo.');
      } else if (msg.includes('422')) {
        setError('Datos inválidos. Revisá los campos e intentá nuevamente.');
      } else {
        setError(`Error: ${msg}`);
      }
    } finally {
      setLoading(false);
    }
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-surface">
      {/* Panel de marca — solo desktop */}
      <aside className="hidden lg:flex flex-col justify-between p-xxl bg-gradient-to-br from-primary to-primary-700 text-on-primary relative overflow-hidden">
        <span className="pointer-events-none absolute -top-16 -right-16 w-72 h-72 rounded-full bg-white/10" aria-hidden />
        <span className="pointer-events-none absolute bottom-10 -left-20 w-80 h-80 rounded-full bg-white/5" aria-hidden />
        <div className="flex items-center gap-sm relative">
          <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center">
            <Icon name="verified_user" className="text-[24px]" fill />
          </div>
          <span className="font-headline text-title-lg">Active Exam</span>
        </div>
        <div className="relative max-w-md">
          <h2 className="font-headline text-display-lg leading-tight">Creá tu cuenta de estudiante.</h2>
          <p className="text-body-lg text-white/80 mt-md">
            Registrate para acceder a los exámenes supervisados de {INSTITUTION.nombre}.
          </p>
        </div>
        <div className="relative flex items-center gap-xs text-label-sm text-white/70">
          <Icon name="lock" className="text-[18px]" fill />
          Self-hosted · DPIA aprobado
        </div>
      </aside>

      {/* Panel de formulario */}
      <main className="flex flex-col items-center justify-center px-lg py-xl">
        <div className="w-full max-w-sm flex flex-col gap-xxl animate-in fade-in slide-in-from-bottom-4 duration-700">

          {/* Encabezado */}
          <header className="flex flex-col items-center gap-md text-center">
            <div className="w-14 h-14 rounded-2xl bg-primary text-on-primary flex items-center justify-center shadow-sm lg:hidden">
              <Icon name="person_add" className="text-[28px]" fill />
            </div>
            <div>
              <h1 className="font-headline text-headline-lg text-on-surface tracking-tight">Crear cuenta</h1>
              <p className="text-body-md text-on-surface-variant mt-xs">
                Completá tus datos para registrarte como estudiante.
              </p>
            </div>
          </header>

          {/* Institución */}
          <div className="flex items-center gap-sm pb-md border-b border-outline-variant/60">
            <div className="w-11 h-11 rounded-xl bg-primary-fixed text-primary flex items-center justify-center shrink-0">
              <Icon name="account_balance" className="text-[22px]" fill />
            </div>
            <div className="min-w-0">
              <p className="text-label-sm text-on-surface-variant">Tu institución</p>
              <p className="text-body-md font-semibold text-on-surface truncate">{INSTITUTION.nombre}</p>
            </div>
          </div>

          {/* Éxito */}
          {exito && (
            <div className="flex items-center gap-sm p-md rounded-xl bg-success-container text-on-success-container">
              <Icon name="check_circle" className="text-[24px] shrink-0" fill />
              <div>
                <p className="font-semibold text-label-md">¡Cuenta creada!</p>
                <p className="text-label-sm">Redirigiendo al inicio de sesión…</p>
              </div>
            </div>
          )}

          {/* Formulario */}
          {!exito && (
            <form onSubmit={handleSubmit} className="flex flex-col gap-md">
              <TextField
                label="Legajo / ID institucional"
                name="id_institucional"
                value={form.id_institucional}
                onChange={cambiar('id_institucional')}
                icon="badge"
                required
                disabled={loading}
                placeholder={`${INSTITUTION.idPrefix}-23-4912`}
                autoComplete="off"
              />

              <div className="grid grid-cols-2 gap-sm">
                <TextField
                  label="Nombre"
                  name="nombre"
                  value={form.nombre}
                  onChange={cambiar('nombre')}
                  icon="person"
                  required
                  disabled={loading}
                  placeholder="Nombre"
                  autoComplete="given-name"
                />
                <TextField
                  label="Apellido"
                  name="apellido"
                  value={form.apellido}
                  onChange={cambiar('apellido')}
                  required
                  disabled={loading}
                  placeholder="Apellido"
                  autoComplete="family-name"
                />
              </div>

              <TextField
                label="Email"
                name="email"
                type="email"
                value={form.email}
                onChange={cambiar('email')}
                icon="email"
                required
                disabled={loading}
                placeholder={`usuario@${INSTITUTION.dominioEmail}`}
                autoComplete="email"
              />

              <TextField
                label="Contraseña"
                name="password"
                type="password"
                value={form.password}
                onChange={cambiar('password')}
                icon="lock"
                required
                disabled={loading}
                placeholder="Mínimo 8 caracteres"
                autoComplete="new-password"
                hint="Mínimo 8 caracteres."
              />

              <TextField
                label="Confirmar contraseña"
                name="password_confirmacion"
                type="password"
                value={form.password_confirmacion}
                onChange={cambiar('password_confirmacion')}
                icon="lock"
                required
                disabled={loading}
                placeholder="Repetí la contraseña"
                autoComplete="new-password"
                error={
                  form.password_confirmacion && form.password !== form.password_confirmacion
                    ? 'Las contraseñas no coinciden.'
                    : undefined
                }
              />

              {error && (
                <div className="flex items-center gap-xs text-error text-body-sm p-sm rounded-lg bg-error-container">
                  <Icon name="error" className="text-[18px] shrink-0" fill />
                  {error}
                </div>
              )}

              <Button
                type="submit"
                disabled={loading || !form.id_institucional || !form.email || !form.password || !form.password_confirmacion}
                size="lg"
                iconRight={loading ? undefined : 'arrow_forward'}
                className="w-full"
              >
                {loading ? (
                  <span className="inline-flex items-center gap-xs">
                    <Icon name="progress_activity" className="ae-spin text-[20px]" />
                    Registrando…
                  </span>
                ) : 'Crear cuenta'}
              </Button>
            </form>
          )}

          {/* Enlace al login */}
          <p className="text-center text-label-sm text-on-surface-variant">
            ¿Ya tenés cuenta?{' '}
            <Link to="/login" className="text-primary font-semibold hover:underline">
              Iniciar sesión
            </Link>
          </p>

          <p className="flex items-center justify-center gap-xs text-label-sm text-on-surface-variant">
            <Icon name="lock" className="text-outline text-[16px]" fill />
            Tu privacidad está protegida — Ley 25.326
          </p>
        </div>
      </main>
    </div>
  );
}
