import { realFetch } from '../apiCore';

export const cuentaApi = {
  async cambiarContrasena(body: {
    // Opcional: en el primer set de un usuario LTI no hay contraseña actual.
    contrasena_actual?: string;
    contrasena_nueva: string;
    // Opcional, SOLO válido en el primer set: el usuario elige su propio
    // username legible (reemplaza el autogenerado).
    nuevo_username?: string;
    // c-78 E-13: cuando se manda `nuevo_username`, el backend devuelve un access
    // token nuevo con ese nombre. Quien llama tiene que adoptarlo
    // (`refrescarAccessToken`) o la app sigue mostrando el username viejo.
  }): Promise<{ ok: boolean; access_token?: string | null }> {
    return await realFetch('/auth/change-password', {
      method: 'PUT',
      body: JSON.stringify(body),
    });
  },
};
