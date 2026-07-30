// `adminApi` — barril. El objeto tenia 537 lineas con ocho dominios distintos;
// ahora cada uno vive en `lib/apiAdmin/` y aca solo se componen. La superficie no
// cambia: `api.adminApi.loQueSea()` sigue igual, porque `api.ts` spreadea esto.
import { estadisticasApi } from './apiAdmin/estadisticas';
import { usuariosApi } from './apiAdmin/usuarios';
import { scoringApi } from './apiAdmin/scoring';
import { detalleUsuarioApi } from './apiAdmin/detalle-usuario';
import { registroApi } from './apiAdmin/registro';
import { consentimientoApi } from './apiAdmin/consentimiento';
import { configSistemaApi } from './apiAdmin/config-sistema';
import { moodleApi } from './apiAdmin/moodle';

export const adminApi = {
  ...estadisticasApi,
  ...usuariosApi,
  ...scoringApi,
  ...detalleUsuarioApi,
  ...registroApi,
  ...consentimientoApi,
  ...configSistemaApi,
  ...moodleApi,
};

// Tipos del dominio Moodle: viven junto a sus metodos y se re-exportan aca
// para que `import { MiCuentaCampus } from '../lib/apiAdmin'` siga andando.
export type { MiCuentaCampus, CredencialMoodle } from './apiAdmin/moodle';
