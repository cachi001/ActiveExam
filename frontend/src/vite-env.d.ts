/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  readonly VITE_USE_REAL_BACKEND?: string;
  readonly VITE_BIOMETRIC_VALIDITY_MONTHS?: string;
  readonly VITE_ENABLE_DNI_SCAN?: string;
  // Identidad institucional (C-27)
  readonly VITE_INSTITUTION_NOMBRE?: string;
  readonly VITE_INSTITUTION_FACULTAD?: string;
  readonly VITE_INSTITUTION_NOMBRE_CORTO?: string;
  readonly VITE_INSTITUTION_SIGLA?: string;
  readonly VITE_INSTITUTION_DOMINIO?: string;
  readonly VITE_INSTITUTION_ID_PREFIX?: string;
  readonly VITE_INSTITUTION_LOGIN_LABEL?: string;
  readonly VITE_INSTITUTION_SOPORTE_LABEL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
