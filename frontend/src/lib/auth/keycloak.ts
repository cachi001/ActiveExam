/**
 * Capa de integración con Keycloak (OIDC / OAuth2 + PKCE).
 *
 * Cliente PÚBLICO `proctoring-spa` del realm `proctoring` (C-52). Authorization
 * Code Flow con PKCE S256. El frontend nunca ve un client secret.
 *
 * Detalle clave: el router de la app es hash-based (#/ruta). Keycloak por defecto
 * devuelve los parámetros OIDC (code/state) en el fragmento (#), lo que COLISIONA
 * con el hash router. Por eso forzamos `responseMode: 'query'` → vuelven en el
 * query string (?code=...), sin pisar la ruta.
 *
 * El cliente es SENSOR NO CONFIABLE (regla de dominio #6): el token se valida
 * server-side. Acá solo lo transportamos y lo mapeamos a Principal para la UI.
 */
import Keycloak from 'keycloak-js';
import type { Principal, Rol } from '../types';

const KC_URL = (import.meta.env.VITE_KEYCLOAK_URL as string) ?? 'http://localhost:8080';
const KC_REALM = (import.meta.env.VITE_KEYCLOAK_REALM as string) ?? 'proctoring';
const KC_CLIENT = (import.meta.env.VITE_KEYCLOAK_CLIENT_ID as string) ?? 'proctoring-spa';

export const keycloak = new Keycloak({ url: KC_URL, realm: KC_REALM, clientId: KC_CLIENT });

/** Roles válidos del modelo MVP. Cualquier rol de Keycloak fuera de esto se ignora. */
const ROLES_VALIDOS: readonly Rol[] = ['estudiante', 'proctor', 'admin_sistema'];

/**
 * Inicializa Keycloak con check-sso silencioso (no fuerza login al cargar la app;
 * detecta si ya hay sesión). Resuelve a `true` si hay sesión activa.
 */
export function initKeycloak(): Promise<boolean> {
  return keycloak.init({
    onLoad: 'check-sso',
    silentCheckSsoRedirectUri: `${window.location.origin}/silent-check-sso.html`,
    pkceMethod: 'S256',
    responseMode: 'query', // evita colisión con el hash router (#/ruta)
    checkLoginIframe: false,
  });
}

/**
 * Mapea el JWT de Keycloak al Principal de dominio. Robusto ante claims ausentes.
 * - id_institucional ← preferred_username (username institucional)
 * - roles ← realm_access.roles (filtrados al modelo MVP)
 * - mfa_satisfecho ← amr incluye otp/totp, o acr ≥ 2 (paso de MFA en el flujo)
 */
export function principalFromToken(): Principal | null {
  const t = keycloak.tokenParsed as Record<string, unknown> | undefined;
  if (!t) return null;

  const realmAccess = t.realm_access as { roles?: string[] } | undefined;
  const realmRoles = realmAccess?.roles ?? [];
  const roles = [...new Set(realmRoles.filter((r): r is Rol => ROLES_VALIDOS.includes(r as Rol)))];

  const amr = Array.isArray(t.amr) ? (t.amr as string[]) : [];
  const acr = t.acr;
  const mfaSatisfecho =
    amr.some((a) => ['otp', 'totp', 'mfa'].includes(a)) || acr === '2' || Number(acr) >= 2;

  return {
    id_institucional: (t.preferred_username as string) ?? (t.sub as string) ?? '',
    nombre: (t.name as string) ?? (t.preferred_username as string) ?? 'Usuario',
    email: (t.email as string) ?? '',
    roles: roles.length ? roles : ['estudiante'],
    mfa_satisfecho: mfaSatisfecho,
    jurisdiccion: (t.jurisdiccion as string) ?? 'AR',
  };
}

/** Redirige a la pantalla de login de Keycloak. Vuelve a la raíz de la SPA. */
export function login(): void {
  void keycloak.login({ redirectUri: `${window.location.origin}/` });
}

/** Cierra la sesión en Keycloak y vuelve a la raíz. */
export function logout(): void {
  void keycloak.logout({ redirectUri: `${window.location.origin}/` });
}

/** Token de acceso vigente (o undefined si no hay sesión). Para el header Authorization. */
export function getToken(): string | undefined {
  return keycloak.token;
}
