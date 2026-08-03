import { realFetch } from '../apiCore';

export const cuentaApi = {
  async cambiarContrasena(body: {
    contrasena_actual: string;
    contrasena_nueva: string;
  }): Promise<{ ok: boolean }> {
    return await realFetch('/auth/change-password', {
      method: 'PUT',
      body: JSON.stringify(body),
    });
  },
};
