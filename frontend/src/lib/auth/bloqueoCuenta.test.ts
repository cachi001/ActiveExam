/**
 * Cuenta regresiva del bloqueo por intentos fallidos.
 *
 * Pedido del dueño (29/8/2026), después de comerse un bloqueo sin entender por
 * qué: si la cuenta se bloquea, hay que decirlo con un reloj a la vista. Antes el
 * login mostraba «Credenciales inválidas» y nada más — el usuario no sabía si se
 * había equivocado, si la app estaba rota, ni cuánto esperar.
 */

import { describe, expect, it } from 'vitest';

import { bloqueoDeLaRespuesta, textoDeEspera } from './bloqueoCuenta';

describe('detectar el bloqueo en la respuesta del login', () => {
  it('reconoce la respuesta de cuenta bloqueada', () => {
    expect(
      bloqueoDeLaRespuesta({
        error: 'cuenta_bloqueada',
        mensaje: 'Cuenta bloqueada…',
        segundos_restantes: 900,
      }),
    ).toBe(900);
  });

  it('una credencial inválida común no es un bloqueo', () => {
    expect(bloqueoDeLaRespuesta('Credenciales inválidas.')).toBeNull();
  });

  it('tolera una respuesta sin la forma esperada', () => {
    // Backend viejo, proxy que reescribe el cuerpo, etc.: no puede romper el login.
    expect(bloqueoDeLaRespuesta(undefined)).toBeNull();
    expect(bloqueoDeLaRespuesta({ error: 'otra_cosa' })).toBeNull();
  });
});

describe('texto de la cuenta regresiva', () => {
  it('sobre el minuto muestra minutos y segundos', () => {
    expect(textoDeEspera(900)).toBe('15:00');
    expect(textoDeEspera(61)).toBe('01:01');
  });

  it('bajo el minuto muestra solo los segundos, para que se sienta cerca', () => {
    // Un «00:09» es más difícil de leer de un vistazo que «9 s» cuando falta poco.
    expect(textoDeEspera(9)).toBe('9 s');
    expect(textoDeEspera(30)).toBe('30 s');
  });

  it('en cero avisa que ya puede intentar', () => {
    expect(textoDeEspera(0)).toBe('ya podés intentar');
  });

  it('no muestra tiempos negativos', () => {
    // El contador puede pasarse si la pestaña estuvo dormida.
    expect(textoDeEspera(-5)).toBe('ya podés intentar');
  });
});
