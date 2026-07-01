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

// Bypass de captura biométrica SOLO en desarrollo: permite saltear el enrollment
// (EnrollmentBiometricStep) y la verificación en vivo (Biometria) sin cámara física.
// NUNCA se activa en un build de producción (import.meta.env.DEV es false ahí).
// Para probar la captura real de cámara EN DEV: VITE_SKIP_BIOMETRIC_CAPTURE=0.
// Riesgo (RN-BIO-05): el backend hoy acepta el embedding client-side sin re-inferir
// en enrollment (D3/C-56), así que este flag NO debe existir fuera de dev.
export const SKIP_BIOMETRIC_CAPTURE =
  import.meta.env.DEV && import.meta.env.VITE_SKIP_BIOMETRIC_CAPTURE === '1';

// Embedding 128-d FIJO usado por el bypass de arriba. Mismo vector en enrollment y
// en verificación en vivo -> distancia coseno 0 -> siempre matchea (umbral 0.35).
// No es un dato biométrico real: es una constante determinística de testing.
export const FAKE_EMBEDDING_128D: number[] = Array.from(
  { length: 128 },
  (_, i) => Math.sin(i + 1),
);
