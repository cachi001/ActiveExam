// Flag de herramientas de desarrollo.
// OFF por default (producción y demos).
// Para habilitar en local: agregá VITE_DEV_TOOLS=1 a .env.local (no commitear).
export const DEV_TOOLS_ENABLED = import.meta.env.VITE_DEV_TOOLS === '1';
