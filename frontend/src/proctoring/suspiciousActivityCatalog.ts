/**
 * Catalogo canonico de actividad sospechosa (C-25, suspicious-activity-catalog).
 *
 * Fuente de verdad para:
 *   - TipoEvento valido del dominio (compatible con event-schema-contract de C-10)
 *   - Severidad por defecto de cada tipo
 *   - Labels y descripciones de UI
 *   - Checklist de cobertura del harness (integral-activity-validation)
 *
 * IMPORTANTE: NINGUN tipo del catalogo implica sancion automatica (L2.5).
 * Los eventos son senales para revision humana asincrónica.
 */

import type { TipoEvento, Severidad } from '../lib/types';

export interface CatalogEntry {
  tipo: TipoEvento;
  severidad: Severidad;
  /** Categoria: 'vision' | 'navegador' */
  categoria: 'vision' | 'navegador';
  /** Etiqueta de UI corta. */
  label: string;
  /** Descripcion larga para tooltip / revisores. */
  descripcion: string;
  /**
   * true si la deteccion depende de una API del navegador que puede estar ausente
   * (p. ej. getScreenDetails para monitores multiples). El harness marca estos
   * items como "no testeable en este navegador" en vez de faltante.
   */
  requiereApiOpcional?: boolean;
}

/**
 * Catalogo canonico. Cada tipo aparece una sola vez.
 * Compatible con el event-schema-contract de C-10 (tipos y severidades).
 */
export const SUSPICIOUS_ACTIVITY_CATALOG: readonly CatalogEntry[] = [
  // --- Vision ---
  {
    tipo: 'rostro_ausente',
    severidad: 'media',
    categoria: 'vision',
    label: 'Rostro ausente',
    descripcion: 'No se detectó rostro en el encuadre por más de 3 segundos.',
  },
  {
    tipo: 'multiples_rostros',
    severidad: 'alta',
    categoria: 'vision',
    label: 'Múltiples rostros',
    descripcion: 'Se detectaron múltiples rostros simultáneos en cámara.',
  },
  {
    tipo: 'mirada_desviada_sostenida',
    severidad: 'media',
    categoria: 'vision',
    label: 'Mirada desviada sostenida',
    descripcion: 'Patrón de mirada sostenido hacia un punto fijo fuera de pantalla.',
  },
  // --- Navegador / entorno ---
  {
    tipo: 'perdida_de_foco',
    severidad: 'baja',
    categoria: 'navegador',
    label: 'Pérdida de foco',
    descripcion: 'El estudiante minimizó la ventana o la ventana perdió el foco del sistema operativo.',
  },
  {
    tipo: 'cambio_pestana',
    severidad: 'media',
    categoria: 'navegador',
    label: 'Cambio de pestaña',
    descripcion: 'El estudiante cambió o abrió otra pestaña del navegador durante el examen.',
  },
  {
    tipo: 'monitor_adicional',
    severidad: 'alta',
    categoria: 'navegador',
    label: 'Monitor adicional',
    descripcion: 'Se detectó un segundo monitor conectado al equipo.',
    requiereApiOpcional: true,
  },
  {
    tipo: 'salida_pantalla_completa',
    severidad: 'media',
    categoria: 'navegador',
    label: 'Salida de pantalla completa',
    descripcion: 'El estudiante salió del modo de pantalla completa durante el examen.',
  },
  {
    tipo: 'copiar_pegar',
    severidad: 'media',
    categoria: 'navegador',
    label: 'Copiar / Pegar',
    descripcion: 'Se detectó una acción de copiar o pegar durante el examen (sin capturar contenido).',
  },
] as const;

/** Mapa tipo → entrada del catalogo para lookups O(1). */
export const CATALOG_BY_TIPO: Readonly<Record<TipoEvento, CatalogEntry>> =
  Object.fromEntries(
    SUSPICIOUS_ACTIVITY_CATALOG.map((e) => [e.tipo, e]),
  ) as Record<TipoEvento, CatalogEntry>;

/** Tipos catalogados de vision (para checklist de cobertura). */
export const VISION_TIPOS: readonly TipoEvento[] = SUSPICIOUS_ACTIVITY_CATALOG
  .filter((e) => e.categoria === 'vision')
  .map((e) => e.tipo);

/** Tipos catalogados de navegador (para checklist de cobertura). */
export const BROWSER_TIPOS: readonly TipoEvento[] = SUSPICIOUS_ACTIVITY_CATALOG
  .filter((e) => e.categoria === 'navegador')
  .map((e) => e.tipo);
