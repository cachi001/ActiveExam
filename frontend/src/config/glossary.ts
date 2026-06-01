/**
 * Glosario central de términos técnicos y legales — C-28.
 * Módulo TypeScript puro (mismo patrón que institution.ts).
 * Importar GLOSSARY directamente; sin hooks ni context providers.
 */

export type TermKey =
  | 'l2_5'
  | 'embedding'
  | 'worm'
  | 'liveness'
  | 'cadena_de_custodia'
  | 'face_mesh'
  | 'datos_biometricos'
  | 'bounding_box'
  | 'gaze_vector'
  | 'pose_keypoints';

export interface GlossaryEntry {
  /** Texto del término tal como aparece en la UI (ej. "L2.5") */
  label: string;
  /** Definición en lenguaje claro, máx. 2 frases */
  definition: string;
  /** Referencia legal opcional (ej. "Ley 25.326, Art. 2") */
  legalRef?: string;
}

export const GLOSSARY: Record<TermKey, GlossaryEntry> = {
  l2_5: {
    label: 'L2.5',
    definition:
      'Nivel de supervisión donde el sistema nunca sanciona automáticamente: solo prioriza casos para revisión. La decisión disciplinaria la toma siempre una persona.',
  },
  embedding: {
    label: 'embedding',
    definition:
      'Representación numérica de la geometría de tu rostro. Se trata como dato sensible y se elimina al egreso. No es una foto.',
    legalRef: 'Ley 25.326, Art. 2',
  },
  worm: {
    label: 'WORM',
    definition:
      'Write Once Read Many: una vez escrito, el archivo no puede modificarse ni borrarse. Garantiza que la evidencia es auténtica.',
  },
  liveness: {
    label: 'liveness',
    definition:
      'Prueba de que hay una persona viva frente a la cámara (no una foto, video ni máscara). Parte de la verificación de identidad.',
  },
  cadena_de_custodia: {
    label: 'cadena de custodia',
    definition:
      'Registro criptográfico que prueba que la evidencia no fue alterada desde su captura hasta la revisión. Cada paso queda firmado.',
  },
  face_mesh: {
    label: 'Face Mesh',
    definition:
      'Malla de 468 puntos del rostro generada por la biblioteca MediaPipe para medir geometría facial. Insumo del embedding.',
  },
  datos_biometricos: {
    label: 'datos biométricos',
    definition:
      'Datos obtenidos de características físicas (aquí: geometría facial). Clasificados como datos sensibles; requieren consentimiento informado explícito.',
    legalRef: 'Ley 25.326',
  },
  bounding_box: {
    label: 'bounding box',
    definition:
      'Área rectangular que rodea a una persona o rostro detectado por la cámara. Se expresa como coordenadas x, y y dimensiones width, height normalizadas entre 0 y 1 (0 = borde izquierdo/superior, 1 = borde derecho/inferior de la imagen).',
  },
  gaze_vector: {
    label: 'vector gaze',
    definition:
      'Estimación de la dirección de la mirada de una persona. Se expresa como dos valores (x, y) entre -1 y 1: valores cercanos a 0 indican que la persona mira al frente; valores extremos indican que mira hacia los costados o arriba/abajo.',
  },
  pose_keypoints: {
    label: 'pose keypoints',
    definition:
      'Puntos de referencia del cuerpo de una persona (hombros, codos, manos, etc.) detectados por un modelo de visión artificial. Su presencia confirma que hay una persona entera visible, no solo el rostro.',
  },
};
