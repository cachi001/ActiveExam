/**
 * Con el escaneo de DNI apagado, la sección no se muestra en absoluto.
 *
 * `ENABLE_DNI_SCAN` está en false por default (requiere `VITE_ENABLE_DNI_SCAN=1`),
 * pero la tarjeta se seguía pintando con la leyenda "No disponible en esta
 * versión". Decisión del dueño (28/8/2026): si la función no existe, no se le
 * anuncia al alumno. Una sección apagada que igual ocupa lugar solo genera la
 * pregunta "¿y esto qué es?" en medio de los requisitos para rendir.
 */

import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

afterEach(() => cleanup());

vi.mock('../../../lib/api', async () => {
  const real = await vi.importActual<typeof import('../../../lib/api')>('../../../lib/api');
  return { ...real, ENABLE_DNI_SCAN: false, api: { ...real.api } };
});

import { PerfilVistaGeneral } from './PerfilVistaGeneral';

const props = {
  principal: {
    username: 'estudiante2',
    nombre: 'Ana',
    apellido: 'Gómez',
    email: 'ana@test.local',
    roles: ['estudiante'],
    foto_perfil: null,
  } as never,
  enrollment: null,
  versionVigente: 'v1',
  consentimientoOk: false,
  biometriaOk: false,
  biometriaCaducada: false,
  biometriaRenovacionRequerida: false,
  dniOk: false,
  perfilCompleto: false,
  onNavigate: () => {},
  onIniciarConsentimiento: () => {},
  onLeerConsentimiento: () => {},
  onIniciarEnrollment: () => {},
  onRenovarBiometria: () => {},
  onSimularDeriva: () => {},
  onRehacerFoto: () => {},
  onEscanearDni: () => {},
};

describe('perfil del alumno con el escaneo de DNI apagado', () => {
  it('no muestra la sección de verificación documental', () => {
    render(<PerfilVistaGeneral {...props} />);
    expect(screen.queryByText(/verificación documental/i)).toBeNull();
  });

  it('no le anuncia al alumno una función que no existe', () => {
    render(<PerfilVistaGeneral {...props} />);
    expect(screen.queryByText(/no disponible en esta versión/i)).toBeNull();
    expect(screen.queryByText(/escanear dni/i)).toBeNull();
  });

  it('sigue mostrando los requisitos que sí existen', () => {
    render(<PerfilVistaGeneral {...props} />);
    expect(screen.queryAllByText(/consentimiento/i).length).toBeGreaterThan(0);
  });
});
