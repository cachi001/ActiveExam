import { realFetch } from '../apiCore';

export const cuentaApi = {
  async cambiarContrasena(body: {
    // Opcional: en el primer set de un usuario LTI no hay contraseña actual.
    contrasena_actual?: string;
    contrasena_nueva: string;
  }): Promise<{ ok: boolean }> {
    return await realFetch('/auth/change-password', {
      method: 'PUT',
      body: JSON.stringify(body),
    });
  },
};
