import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'
import { authProvider, AUTH_PROVIDER_TYPE } from './lib/authProvider'
import { useAuth } from './lib/authStore'
import { useApp } from './lib/store'
import { AUTH_BYPASS } from './lib/devConfig'

// Espeja el principal de auth (useAuth, fuente de verdad) hacia useApp, que es lo
// que leen las pantallas legacy (Hola {nombre}, sidebar, etc.). Suscripto ANTES del
// init para capturar la hidratación inicial. Evita migrar cada pantalla a useAuth.
useAuth.subscribe((state) => {
  useApp.getState().setPrincipal(state.principal, state.principal?.roles[0] ?? null)
})

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
    // Provider no disponible (Keycloak caído, red sin token, etc.):
    // la app carga igual y muestra el login.
    console.warn(`[auth] Provider "${AUTH_PROVIDER_TYPE}" no disponible:`, err)
    useAuth.setState({ status: 'unauthenticated' })
  })
  .finally(() => {
    // Bypass de desarrollo: si no quedó sesión real y el bypass está activo,
    // inyecta un principal dev. Inerte en producción.
    if (AUTH_BYPASS && useAuth.getState().status !== 'authenticated') {
      console.info('[auth] AUTH_BYPASS activo: navegando con principal dev')
      useAuth.getState().enableDevBypass()
    }
    render()
  })
