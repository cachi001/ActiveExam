import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'
import { initKeycloak, keycloak } from './lib/auth/keycloak'
import { useAuth } from './lib/authStore'
import { useApp } from './lib/store'
import { AUTH_BYPASS, DEMO_MODE } from './lib/devConfig'

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

if (DEMO_MODE) {
  // Modo demo (Vercel sin Keycloak): no inicializamos Keycloak. El Login muestra
  // un selector de rol y entra con un principal demo (useAuth.loginDemo).
  console.info('[auth] DEMO_MODE activo: login con selector de rol (sin Keycloak)')
  useAuth.setState({ status: 'unauthenticated' })
  render()
} else {
  // Mantiene el authStore en sync con Keycloak (login, refresh, logout, expiración).
  keycloak.onAuthSuccess = () => useAuth.getState().hydrateFromKeycloak()
  keycloak.onAuthRefreshSuccess = () => useAuth.getState().hydrateFromKeycloak()
  keycloak.onAuthLogout = () => useAuth.getState().hydrateFromKeycloak()
  keycloak.onTokenExpired = () => {
    // Refresca el token si le quedan < 30s de validez; re-hidrata al renovar.
    void keycloak.updateToken(30).then(() => useAuth.getState().hydrateFromKeycloak())
  }

  initKeycloak()
    .then(() => useAuth.getState().hydrateFromKeycloak())
    .catch((err) => {
      // Keycloak no disponible (p. ej. stack Docker no levantado): la app igual
      // carga y muestra el login; el botón intentará conectar al hacer click.
      console.warn('[auth] Keycloak no disponible, modo desconectado:', err)
      useAuth.setState({ status: 'unauthenticated' })
    })
    .finally(() => {
      // Bypass de desarrollo: si no quedó sesión real y el bypass está activo (dev),
      // inyecta un principal dev para poder navegar sin Keycloak. Inerte en producción.
      if (AUTH_BYPASS && useAuth.getState().status !== 'authenticated') {
        console.info('[auth] AUTH_BYPASS activo: navegando con principal dev (sin Keycloak)')
        useAuth.getState().enableDevBypass()
      }
      render()
    })
}
