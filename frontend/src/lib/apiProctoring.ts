// `proctoringApi` — barril. El objeto tenia 509 lineas y 22 metodos de seis
// dominios distintos; ahora cada uno vive en `lib/apiProctoring/`. La superficie no
// cambia: `api.ts` spreadea esto igual que antes.
import { sesionApi } from './apiProctoring/sesion';
import { respuestasApi } from './apiProctoring/respuestas';
import { chatApi } from './apiProctoring/chat';
import { pausasApi } from './apiProctoring/pausas';
import { observacionesApi } from './apiProctoring/observaciones';
import { revisionApi } from './apiProctoring/revision';

export const proctoringApi = {
  ...sesionApi,
  ...respuestasApi,
  ...chatApi,
  ...pausasApi,
  ...observacionesApi,
  ...revisionApi,
};
