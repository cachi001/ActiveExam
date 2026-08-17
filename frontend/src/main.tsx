import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'
import { authProvider, AUTH_PROVIDER_TYPE } from './lib/authProvider'
import { useAuth } from './lib/authStore'
import { registerModelCacheWorker } from './lib/modelPersistence'

// C-67 fix: cachear de forma persistente los modelos de IA (MediaPipe + face-api)
// vía Service Worker, para que se bajen una sola vez y no se re-descarguen en cada
// captura biométrica (eliminaba el cuelgue/crash en el teléfono).
registerModelCacheWorker()

// Material Symbols leaks: en conexiones lentas (túnel cloudflared) el font CSS
// con `display=block` deja ver el nombre del ligature ("verification", "home", …)
// tras ~3s. Marcamos `<html>` con `ms-ready` cuando la fuente realmente cargó —
// el CSS oculta los iconos hasta entonces. Fallback a 5s si `document.fonts`
// no resuelve (entornos sin Font Loading API).
const markIconsReady = () => document.documentElement.classList.add('ms-ready');
const fonts = (document as Document & { fonts?: FontFaceSet }).fonts;
if (fonts) {
  fonts.load('24px "Material Symbols Outlined"').then(markIconsReady).catch(markIconsReady);
  window.setTimeout(markIconsReady, 5000);
} else {
  markIconsReady();
}

function render() {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  )
}

// Escuchar cambios de auth del provider activo → re-hidratar el store.
authProvider.onAuthChange(() => {
  useAuth.getState().hydrateFromProvider(authProvider)
})

// Inicializar el provider activo (check-sso, recuperar token de storage, etc.).
authProvider.init()
  .then(() => {
    useAuth.getState().hydrateFromProvider(authProvider)
  })
  .catch((err) => {
    // Provider no disponible (backend caído, red sin token, etc.):
    // la app carga igual y muestra el login.
    console.warn(`[auth] Provider "${AUTH_PROVIDER_TYPE}" no disponible:`, err)
    useAuth.setState({ status: 'unauthenticated' })
  })
  .finally(() => {
    // Sin bypass: si no hay sesión real, la app muestra el login. No hay atajo
    // para navegar sin autenticarse (ni en dev ni en prod).
    render()
  })
