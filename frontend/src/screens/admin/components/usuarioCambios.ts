// ¿El formulario de edición tiene algo distinto de lo que se cargó?
//
// El botón "Guardar cambios" estaba siempre activo, incluso recién abierta la
// pantalla sin tocar nada. Ofrecer guardar lo que no cambió invita a un PATCH
// inútil que igual queda auditado y, sobre todo, borra la única señal de si uno
// modificó algo — que es justo lo que se quiere saber antes de confirmar cambios de
// ROLES sobre la cuenta de otra persona.
import type { FormState } from './UsuarioHelpers';
import type { UsuarioAdmin } from '../../../lib/types';

/** `null` y `""` son lo mismo acá: el backend devuelve null cuando el campo está
 *  vacío y el formulario lo representa como string vacío. Tratarlos distinto
 *  marcaría como sucio un formulario que nadie tocó. */
const texto = (v: string | null | undefined) => (v ?? '').trim();

export function hayCambios(original: UsuarioAdmin | null, form: FormState): boolean {
  if (!original) return false;

  if (texto(form.email) !== texto(original.email)) return true;
  if (texto(form.nombre) !== texto(original.nombre)) return true;
  if (texto(form.apellido) !== texto(original.apellido)) return true;

  // Los roles se comparan como CONJUNTO: los checkboxes los agregan en el orden en
  // que se tocan, así que destildar y volver a tildar el mismo rol cambia el orden
  // del array sin cambiar nada real.
  const antes = [...(original.roles ?? [])].sort();
  const ahora = [...form.roles].sort();
  return antes.length !== ahora.length || antes.some((r, i) => r !== ahora[i]);
}

export default hayCambios;
