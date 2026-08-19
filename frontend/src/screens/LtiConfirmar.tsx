/**
 * LtiConfirmar — confirmación de alta pendiente del launch LTI (primer ingreso).
 *
 * Antes, un launch LTI que resultaba en una cuenta NUEVA se auto-provisionaba
 * y logueaba en el mismo request, sin ningún paso intermedio (bug real
 * 2026-08-19: el dueño del proyecto entró con su cuenta ADMIN de Moodle y
 * quedó logueado como alumno sin haber confirmado nada). Ahora el backend
 * redirige acá con un `pendiente_id` de un solo uso (corta vida) en vez de
 * loguear directo — recién si el usuario confirma se crea la cuenta.
 *
 * Un REINGRESO (cuenta ya existente) NUNCA pasa por acá — sigue logueando
 * directo desde `/lti-login`, sin fricción.
 *
 * `nombre`/`email` vienen en el fragment SOLO para mostrarlos — quien decide
 * qué cuenta se crea es el backend, con los claims que ya validó y guardó
 * contra `pendiente_id` (no lo que diga esta URL).
 */
import { useEffect, useState } from 'react';
import { useAuth } from '../lib/authStore';
import { useNavigate } from '../lib/router';
import { Icon } from '../ui/components';
import { API_BASE } from '../lib/apiCore';

type Estado = 'confirmando' | 'enviando' | 'error';

export default function LtiConfirmar() {
  const loginWithTokens = useAuth((s) => s.loginWithTokens);
  const navigate = useNavigate();
  const [estado, setEstado] = useState<Estado>('confirmando');
  const [error, setError] = useState<string | null>(null);
  const [pendienteId, setPendienteId] = useState<string | null>(null);
  const [nombre, setNombre] = useState('');
  const [email, setEmail] = useState('');

  useEffect(() => {
    const hashParams = new URLSearchParams(window.location.hash.replace(/^#/, ''));
    const id = hashParams.get('pendiente_id');
    if (!id) {
      setError('El enlace de confirmación no es válido.');
      setEstado('error');
      return;
    }
    setPendienteId(id);
    setNombre(hashParams.get('nombre') ?? 'tu cuenta');
    setEmail(hashParams.get('email') ?? '');
  }, []);

  async function confirmar() {
    if (!pendienteId) return;
    setEstado('enviando');
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/lti/confirmar-provisioning`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pendiente_id: pendienteId }),
      });
      if (!res.ok) {
        if (res.status === 410) {
          throw new Error('Este enlace de confirmación venció o ya se usó. Volvé a entrar desde Moodle.');
        }
        throw new Error('No pudimos crear tu cuenta. Volvé a entrar desde Moodle.');
      }
      const data = (await res.json()) as { access_token: string; refresh_token: string };
      const ok = loginWithTokens(data.access_token, data.refresh_token);
      if (!ok) throw new Error('No pudimos iniciar tu sesión.');
      window.history.replaceState({}, '', '/alumno');
      navigate('/alumno');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No pudimos crear tu cuenta.');
      setEstado('error');
    }
  }

  if (estado === 'error') {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-md bg-surface px-lg text-center">
        <div className="w-14 h-14 rounded-2xl bg-error-container text-error flex items-center justify-center">
          <Icon name="link_off" className="text-[28px]" fill />
        </div>
        <div>
          <h1 className="font-headline text-headline-md text-on-surface">No pudimos crear tu cuenta</h1>
          <p className="text-body-md text-on-surface-variant mt-base max-w-sm">{error}</p>
          <button className="mt-lg text-primary underline" onClick={() => navigate('/login')}>
            Ir al inicio de sesión
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-lg bg-surface px-lg text-center">
      <div className="w-14 h-14 rounded-2xl bg-primary/15 text-primary flex items-center justify-center">
        <Icon name="person_add" className="text-[28px]" fill />
      </div>
      <div className="max-w-sm space-y-sm">
        <h1 className="font-headline text-headline-md text-on-surface">Confirmá tu cuenta</h1>
        <p className="text-body-md text-on-surface-variant">
          Vas a crear una cuenta nueva en ActiveExam como <strong className="text-on-surface">{nombre}</strong>
          {email && (
            <>
              {' '}con el correo <strong className="text-on-surface">{email}</strong>
            </>
          )}
          .
        </p>
      </div>
      <div className="flex items-center gap-md">
        <button
          type="button"
          className="text-on-surface-variant underline"
          onClick={() => navigate('/login')}
          disabled={estado === 'enviando'}
        >
          Cancelar
        </button>
        <button
          type="button"
          onClick={confirmar}
          disabled={estado === 'enviando'}
          className="inline-flex items-center gap-sm rounded-xl bg-primary text-on-primary px-lg py-sm font-medium disabled:opacity-60"
        >
          {estado === 'enviando' && <Icon name="progress_activity" className="ae-spin text-[18px]" />}
          Continuar
        </button>
      </div>
    </div>
  );
}
