// Flag de herramientas de desarrollo.
// OFF por default (producción y demos).
// Para habilitar en local: agregá VITE_DEV_TOOLS=1 a .env.local (no commitear).
export const DEV_TOOLS_ENABLED = import.meta.env.VITE_DEV_TOOLS === '1';

// Bypass de autenticación SOLO en desarrollo: permite navegar la app sin Keycloak
// levantado (con un principal dev de todos los roles). NUNCA se activa en un build
// de producción (import.meta.env.DEV es false ahí), así que es imposible saltear
// la auth en prod. Para probar el login OIDC real EN DEV: VITE_AUTH_BYPASS=0.
export const AUTH_BYPASS = import.meta.env.DEV && import.meta.env.VITE_AUTH_BYPASS !== '0';

// Modo demo (sirve en PRODUCCIÓN, ej. Vercel sin Keycloak deployado): el login no
// redirige a Keycloak, muestra un selector de rol y entra con un principal demo.
// Se activa con VITE_DEMO_MODE=1. La auth Keycloak real queda intacta cuando está OFF.
export const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === '1';
