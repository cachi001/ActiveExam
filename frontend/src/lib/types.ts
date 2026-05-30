// Tipos de dominio del MVP ActiveExam. Calcados de los schemas del backend
// (app/presentation/api/v1/*). Nombres y enums en español, igual que la API real.

export type Rol =
  | 'estudiante'
  | 'proctor'
  | 'revisor'
  | 'admin_examenes'
  | 'coordinador';

export type Severidad = 'baseline' | 'baja' | 'media' | 'alta' | 'critica';

// tipos de evento discreto emitidos por el pipeline de visión (stateTransitionRules.ts)
export type TipoEvento =
  | 'rostro_ausente'
  | 'multiples_rostros'
  | 'mirada_desviada_sostenida'
  | 'perdida_de_foco'
  | 'monitor_adicional'
  | 'corte_conectividad_prolongado';

export interface Principal {
  id_institucional: string;
  nombre: string;
  email: string;
  roles: Rol[];
  mfa_satisfecho: boolean;
  jurisdiccion: string;
}

export interface BloqueConsentimiento {
  titulo: string;
  cuerpo: string;
  icono: string; // material symbol
}

export interface ConsentTextResponse {
  version: string;
  bloques: BloqueConsentimiento[];
  hash_texto: string;
}

export interface ConsentResponse {
  id: string;
  user_id: string;
  exam_id: string;
  version_texto: string;
  timestamp: string;
  hash: string;
}

export interface Examen {
  id: string;
  nombre: string;
  catedra: string;
  estado: 'borrador' | 'programado' | 'en_curso' | 'finalizado';
  inicio: string; // ISO
  duracion_min: number;
  umbral_score: number; // umbral de cola de revisión
  detectores: TipoEvento[];
  retencion_dias: number;
  inscriptos: number;
  rindiendo: number;
}

export interface DesafioActivo {
  id: 'girar_izquierda' | 'girar_derecha' | 'parpadear' | 'acercarse' | 'sonreir';
  label: string;
}

export interface VerifyIdentityResponse {
  veredicto: 'verificado' | 'reintento' | 'escalado';
  distancia: number;
  reintentos_restantes: number;
  clave_sesion_emitida: boolean;
  escalado_a_proctor: boolean;
}

export interface EventoSesion {
  id: string;
  tipo: TipoEvento;
  severidad: Severidad;
  ts_backend: string; // ISO
  descripcion: string;
  tiene_evidencia: boolean;
  evidencia_object_key?: string;
}

export interface SesionEnVivo {
  id: string;
  estudiante: string;
  legajo: string;
  estado: 'rindiendo' | 'verificando' | 'escalado' | 'desconectado' | 'finalizado';
  score: number;
  anomalias: number;
  ultima_senal: string;
  foto: string;
  es_propia?: boolean;
}

export interface SesionRevision {
  id: string;
  estudiante: string;
  legajo: string;
  examen: string;
  catedra: string;
  score: number;
  fecha: string;
  duracion: string;
  foto: string;
  decision: 'pendiente' | 'descartada' | 'escalada' | 'derivada';
  eventos: EventoSesion[];
  cadena_custodia: {
    hash_cliente: string;
    rehash_backend: string;
    coincide: boolean;
    firma_maestra: string;
    algoritmo_firma: string;
  };
}

export interface ResumenReportes {
  examenes_totales: number;
  sesiones_totales: number;
  tasa_flag: number; // %
  falsos_positivos: number; // %
  tiempo_medio_revision: string;
  distribucion_severidad: { severidad: Severidad; cantidad: number }[];
  tendencia_semanal: { semana: string; flaggeadas: number; revisadas: number }[];
}
