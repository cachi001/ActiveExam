// A dónde entra cada rol al sistema. Fuente ÚNICA.
//
// Vivía privada en `Login.tsx` y estaba duplicada a mano en su propio test, con un
// comentario que reconocía la copia. Las dos versiones ya habían divergido: la real
// mandaba al tutor a `/admin/examenes`, la del test ni contemplaba al tutor. Un test
// que valida una copia no prueba nada sobre la función que corre en producción.
//
// La usan el login (a dónde ir tras autenticar) y la pantalla de "Sin permisos" (a
// dónde vuelve el botón). Ese segundo uso es el que faltaba: navegaba a `/login`,
// pero con el usuario YA autenticado el login lo rebotaba a su home, y si esa home
// era la ruta sin permiso, quedaba en un bucle sin salida salvo cerrar sesión.
import type { Rol } from '../types';

// Roles con acceso al área académica (`/admin` = ACADEMICO en App.tsx: tutor,
// profesor, coordinador, admin_sistema). Cualquiera de ellos entra al panel.
//
// OJO al elegir el destino: tiene que ser una ruta que el rol PUEDA ver. Mandar al
// tutor a `/admin/examenes` —que exige crear exámenes, capacidad que perdió en
// c-78— lo dejaba con "Sin permisos" apenas entraba, sin poder usar el sistema.
const ROLES_DE_STAFF: Rol[] = ['admin_sistema', 'coordinador', 'profesor', 'tutor'];

export function homePorRol(roles: Rol[]): string {
  if (roles.some((r) => ROLES_DE_STAFF.includes(r))) return '/admin';
  // Default deliberadamente restrictivo: el portal del alumno no exige ninguna
  // capacidad, así que nadie queda encerrado por no matchear ningún rol conocido.
  return '/alumno';
}

export default homePorRol;
