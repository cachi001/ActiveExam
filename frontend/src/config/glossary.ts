/**
 * Glosario central de términos técnicos y legales — C-28.
 * Módulo TypeScript puro (mismo patrón que institution.ts).
 * Importar GLOSSARY directamente; sin hooks ni context providers.
 */

export type TermKey =
  | 'embedding'
  | 'worm'
  | 'liveness'
  | 'cadena_de_custodia'
  | 'face_mesh'
  | 'datos_biometricos'
  | 'bounding_box'
  | 'gaze_vector'
  | 'pose_keypoints'
  // C-67 Grupo 6: términos para el detalle técnico colapsado de verificación 1:1
  | 'similitud_coseno'
  | 'umbral_verificacion';

export interface GlossaryEntry {
  /** Texto del término tal como aparece en la UI (ej. "L2.5") */
  label: string;
  /** Definición en lenguaje claro, máx. 2 frases */
  definition: string;
}

export const GLOSSARY: Record<TermKey, GlossaryEntry> = {
  embedding: {
    label: 'embedding',
    definition:
      'Representación numérica de la geometría de tu rostro. Se trata como dato sensible y vale 24 meses: al vencer se rehace la captura. No es una foto.',
  },
  worm: {
    label: 'WORM',
    definition:
      'Write Once Read Many: una vez escrito, el archivo no puede modificarse ni borrarse. Garantiza que la evidencia es auténtica.',
  },
  liveness: {
    label: 'Verificación de presencia',
    definition:
      'Confirma que hay una persona real frente a la cámara (no una foto, un video ni una máscara). Es parte de la verificación de tu identidad.',
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
      'Datos obtenidos de características físicas (aquí: geometría facial). Se tratan como datos sensibles; requieren consentimiento informado explícito.',
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
  // C-67 Grupo 6: términos del detalle técnico colapsado de verificación 1:1
  similitud_coseno: {
    label: 'similitud',
    definition:
      'Número entre 0 y 1 que mide qué tan parecida es la imagen capturada a la foto de referencia. Cuanto más cerca de 1, más similitud. Es una señal de conveniencia; la verificación definitiva la hace el servidor.',
  },
  umbral_verificacion: {
    label: 'referencia mínima',
    definition:
      'Valor mínimo de similitud que se necesita para considerar que la imagen coincide con la foto registrada. Configurado de forma conservadora para proteger la identidad del alumno.',
  },
};
