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
  | 'datos_biometricos';

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
};
