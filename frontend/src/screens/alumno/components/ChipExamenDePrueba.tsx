/**
 * ChipExamenDePrueba — marca un examen que es un ensayo (migración 0105).
 *
 * Vive en un componente propio porque el mismo aviso tiene que verse EN TODOS
 * los lugares donde el alumno se cruza con el examen: la lista de "Mis exámenes"
 * y la tarjeta del inicio. Cuando estaba escrito a mano en una sola pantalla,
 * en la otra no aparecía y el examen se leía como real.
 *
 * Dice solo "Examen de prueba": el "no cuenta" que tenía antes sobraba. Que un
 * ensayo no cuente ya está implícito, y en un chip de 11px cada palabra de más
 * resta legibilidad.
 *
 * Sobre el color: usa `warning-800` sobre `warning-100`. La primera versión usaba
 * `text-on-warning-container`, una clase que NO EXISTE en la config de Tailwind
 * de este proyecto (hay `warning.container` para el fondo, pero ningún token de
 * texto), así que Tailwind la descartaba y el texto quedaba en negro heredado.
 * Los tokens que sí existen son la escala `warning-50…900`.
 */

export function ChipExamenDePrueba({ className = '' }: { className?: string }) {
  return (
    <span
      className={
        'inline-flex items-center rounded-full border border-warning-300 bg-warning-100 ' +
        'px-2 py-0.5 text-[11px] font-medium text-warning-800 ' +
        className
      }
    >
      Examen de prueba
    </span>
  );
}
