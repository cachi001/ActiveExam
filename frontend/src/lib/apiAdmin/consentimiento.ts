// Parte de `adminApi`, partido por dominio (mismo criterio que el refactor c-76
// que saco estos metodos de `api.ts`). Se compone en `../apiAdmin.ts` por spread;
// ningun metodo usa `this`.
import { realFetch, normalizarConsentText } from '../apiCore';
import type {
  BloqueConsentimiento,
} from '../types';

export const consentimientoApi = {
  // -------------------------------------------------------------------------
  // Versiones del texto de consentimiento (admin) — C-68
  // -------------------------------------------------------------------------

  /**
   * Lista las versiones publicadas del texto de consentimiento (admin_sistema).
   * Real: GET /api/v1/consent/text/versions
   * Mock: devuelve la versión demo como única entrada.
   */
  async listarVersionesConsentimiento(): Promise<{ version: string; hash_texto: string }[]> {
    return await realFetch<{ version: string; hash_texto: string }[]>(
      '/consent/text/versions',
      { method: 'GET' },
    );
  },

  /**
   * Publica una nueva versión del texto de consentimiento (admin_sistema).
   * Real: POST /api/v1/consent/text/versions
   *   body: { version, bloques: [{titulo, cuerpo}] }
   *   → 200 { version, bloques, hash_texto }
   *   → 409 si la versión ya existe
   * Mock: guarda en memoria (actualiza CONSENT_TEXT para la sesión).
   *
   * La versión publicada no se activa hasta hacer PATCH /config { consent_version_vigente }.
   */
  async crearVersionConsentimiento(params: {
    version: string;
    bloques: Array<{ titulo: string; cuerpo: string }>;
  }): Promise<{ version: string; bloques: BloqueConsentimiento[]; hash_texto: string }> {
    const raw = await realFetch<unknown>(
      '/consent/text/versions',
      { method: 'POST', body: JSON.stringify(params) },
    );
    return normalizarConsentText(raw);
  },
};
