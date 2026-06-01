export interface InstitutionConfig {
  /** Nombre completo de la institución (ej: "Universidad Tecnológica Nacional") */
  nombre: string;
  /** Nombre de la facultad / regional (ej: "Facultad Regional Mendoza") */
  facultad: string;
  /** Nombre corto para UI (ej: "UTN FRM") */
  nombreCorto: string;
  /** Sigla de la regional (ej: "FRM") */
  sigla: string;
  /** Dominio de email institucional (ej: "frm.utn.edu.ar") */
  dominioEmail: string;
  /** Prefijo para IDs de exámenes, staff, etc. (ej: "FRM") */
  idPrefix: string;
  /** Label del botón de ingreso (ej: "UTN FRM ID") */
  loginLabel: string;
  /** Label del link de soporte en el footer (ej: "Soporte UTN FRM") */
  soporteLabel: string;
}

export const INSTITUTION: InstitutionConfig = {
  nombre: import.meta.env.VITE_INSTITUTION_NOMBRE ?? 'Universidad Tecnológica Nacional',
  facultad: import.meta.env.VITE_INSTITUTION_FACULTAD ?? 'Facultad Regional Mendoza',
  nombreCorto: import.meta.env.VITE_INSTITUTION_NOMBRE_CORTO ?? 'UTN FRM',
  sigla: import.meta.env.VITE_INSTITUTION_SIGLA ?? 'FRM',
  dominioEmail: import.meta.env.VITE_INSTITUTION_DOMINIO ?? 'frm.utn.edu.ar',
  idPrefix: import.meta.env.VITE_INSTITUTION_ID_PREFIX ?? 'FRM',
  loginLabel: import.meta.env.VITE_INSTITUTION_LOGIN_LABEL ?? 'UTN FRM ID',
  soporteLabel: import.meta.env.VITE_INSTITUTION_SOPORTE_LABEL ?? 'Soporte UTN FRM',
};
