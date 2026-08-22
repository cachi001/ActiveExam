/**
 * `fetch` que sobrevive al vencimiento del access token.
 *
 * El access token propio vive 15 minutos (`ACCESS_TOKEN_TTL_SECONDS`). Cuando
 * vence, `JwtAdapter._getStoredToken()` lo borra de sessionStorage y
 * `getToken()` pasa a devolver `undefined`: el request sale SIN header
 * `Authorization` y el backend contesta 401 "Falta el Bearer token."
 * (`api/v1/auth/dependencies.py`). El refresh_token, en cambio, sigue vivo 7
 * días y nadie lo estaba usando.
 *
 * `realFetch` (apiCore) ya resolvía esto para las pantallas de alumno desde
 * C-67, pero los clientes de API admin arman el `fetch` a mano y quedaron
 * afuera: al tutor le explotaba cualquier guardado después de 15 minutos con la
 * pantalla abierta (bug real 2026-08-22, "Guardar destino" en el detalle del
 * examen).
 *
 * Contrato: un solo reintento. Si el refresh no devuelve token fresco se
 * propaga la respuesta original para que el caller muestre su propio error;
 * reintentar sin credencial nueva sólo duplicaría el 401.
 */

import { authProvider } from './authProvider';

export async function fetchAutenticado(
  url: string,
  init: RequestInit = {},
): Promise<Response> {
  const res = await fetch(url, init);

  if (res.status !== 401 || !authProvider.refresh) return res;

  const fresco = await authProvider.refresh();
  if (!fresco) return res;

  return await fetch(url, {
    ...init,
    headers: {
      ...(init.headers as Record<string, string> | undefined),
      Authorization: `Bearer ${fresco}`,
    },
  });
}
