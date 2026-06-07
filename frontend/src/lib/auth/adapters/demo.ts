/**
 * DemoAdapter — adapter del modo demo (C-55, D6).
 *
 * Porta el comportamiento actual del selector de roles demo sin red.
 * getToken() retorna 'demo' (valor estático que el backend ignora en modo demo).
 * No persiste sesión — el estado vive solo en memoria.
 *
 * Selección: VITE_AUTH_PROVIDER=demo (o VITE_DEMO_MODE=1 que activa el mismo modo).
 */
import type { AuthProvider, AuthStatus } from '../provider';
import type { Principal, Rol } from '../../types';
import { INSTITUTION } from '../../../config/institution';

const DEMO_PRINCIPALS: Record<Rol, Principal> = {
  estudiante: {
    id_institucional: 'FRM-23-4912',
    nombre: 'Emiliano Cáceres',
    email: 'ecaceres@frm.utn.edu.ar',
    roles: ['estudiante'],
    mfa_satisfecho: true,
    jurisdiccion: 'AR-MZA',
  },
  proctor: {
    id_institucional: `${INSTITUTION.idPrefix}-DOC-1182`,
    nombre: 'Dra. Carolina Ferreyra',
    email: `cferreyra@${INSTITUTION.dominioEmail}`,
    roles: ['proctor'],
    mfa_satisfecho: true,
    jurisdiccion: 'AR',
  },
  admin_sistema: {
    id_institucional: `${INSTITUTION.idPrefix}-ADM-0021`,
    nombre: 'Lucía Mendoza',
    email: `lmendoza@${INSTITUTION.dominioEmail}`,
    roles: ['admin_sistema'],
    mfa_satisfecho: true,
    jurisdiccion: 'AR',
  },
};

export class DemoAdapter implements AuthProvider {
  private _principal: Principal | null = null;
  private _listeners: Array<(status: AuthStatus) => void> = [];

  async init(): Promise<void> {
    // Demo: no hay sesión persistente — comenzar sin autenticar.
    this._notify('unauthenticated');
  }

  async login(creds?: { username: string; password: string }): Promise<void> {
    // En demo el "login" es por rol — ignorar creds.
    // El Login.tsx en modo demo muestra el selector de rol y llama loginDemo directamente.
    void creds;
  }

  /** Inicia sesión demo con el rol dado (llamado desde authStore.loginDemo). */
  loginConRol(rol: Rol): void {
    this._principal = DEMO_PRINCIPALS[rol] ?? null;
    this._notify('authenticated');
  }

  async logout(): Promise<void> {
    this._principal = null;
    this._notify('unauthenticated');
  }

  getToken(): string | undefined {
    return this._principal ? 'demo' : undefined;
  }

  getPrincipal(): Principal | null {
    return this._principal;
  }

  onAuthChange(cb: (status: AuthStatus) => void): () => void {
    this._listeners.push(cb);
    return () => {
      this._listeners = this._listeners.filter((l) => l !== cb);
    };
  }

  private _notify(status: AuthStatus): void {
    this._listeners.forEach((l) => l(status));
  }
}
