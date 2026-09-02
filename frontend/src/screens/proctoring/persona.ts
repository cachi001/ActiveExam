/**
 * Quién es la persona de una sesión, y cómo encontrarla.
 *
 * ## Por qué existe
 *
 * En supervisión en vivo, las tarjetas mostraban `etiqueta`, que **la manda el
 * cliente** (`useExamProctoring` envía el nombre del alumno, y si no lo tiene
 * cargado, el título del examen). Dos problemas, los dos serios con 40 personas
 * rindiendo:
 *
 * - el tutor podía terminar mirando 40 tarjetas que decían todas
 *   "Parcial 1 — Programación III", sin forma de saber quién es quién
 * - el cliente es un sensor no confiable (regla dura #6): esa etiqueta puede
 *   decir cualquier cosa, incluso el nombre de otra persona
 *
 * El servidor SÍ resuelve la identidad contra `usuario`. Estas funciones la
 * prefieren siempre, y dejan la etiqueta como fallback para sesiones que no la
 * tengan resuelta.
 *
 * FUNCIONES PURAS: sin React, sin red.
 */
import type { SesionProctoringResumen } from '../../lib/types';

/** Lo que se muestra cuando no hay ni identidad del servidor ni etiqueta usable. */
export const SIN_IDENTIFICAR = 'Sin identificar';

/**
 * Nombre a mostrar: primero el que resolvió el servidor, después la etiqueta.
 *
 * Nunca inventa: si no hay nada, lo dice. Un nombre inventado en el panel del
 * tutor es peor que un "sin identificar" honesto, porque se actúa sobre él.
 */
export function nombrePersona(s: SesionProctoringResumen): string {
  const delServidor = s.alumno_nombre?.trim();
  if (delServidor) return delServidor;
  const delCliente = s.etiqueta?.trim();
  if (delCliente) return delCliente;
  return SIN_IDENTIFICAR;
}

/** Inicial para el avatar. Sin identidad usa un signo, no una letra engañosa. */
export function inicialDe(s: SesionProctoringResumen): string {
  const nombre = nombrePersona(s);
  if (nombre === SIN_IDENTIFICAR) return '?';
  return nombre.charAt(0).toUpperCase();
}

/** Saca tildes y baja a minúsculas, para comparar como escribe una persona apurada. */
function normalizar(texto: string): string {
  return texto
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase();
}

/**
 * ¿Esta sesión coincide con lo que el docente escribió en el buscador?
 *
 * Busca por nombre, legajo (`alumno_idnumber`, que es como el docente los llama)
 * y correo, más la etiqueta para las sesiones sin identidad resuelta. Sin texto,
 * entran todas.
 */
export function coincideBusqueda(s: SesionProctoringResumen, texto: string): boolean {
  const q = normalizar(texto.trim());
  if (!q) return true;
  return [s.alumno_nombre, s.alumno_idnumber, s.alumno_email, s.etiqueta]
    .filter((campo): campo is string => typeof campo === 'string' && campo.trim() !== '')
    .some((campo) => normalizar(campo).includes(q));
}
