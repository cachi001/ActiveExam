/**
 * Conserva el scroll del menú lateral entre pantallas.
 *
 * ## El problema
 *
 * Cada pantalla monta su PROPIO `<StaffShell>`. Al navegar, React desmonta el
 * shell anterior y monta uno nuevo, así que el contenedor scrolleable del menú
 * nace con `scrollTop = 0`. Con el menú largo (Configuración e Integración LTI
 * están al final), tocar una de esas opciones hacía que el menú saltara solo
 * hacia arriba y perdieras de vista justo lo que acababas de tocar.
 *
 * No lo causaba `ScrollToTop` del router: ese mueve `window`, no este contenedor.
 *
 * ## Por qué acá y no en el shell
 *
 * La posición tiene que sobrevivir al desmontaje, así que no puede vivir en el
 * estado de React del componente que se destruye. Un módulo suelto es lo más
 * simple que cumple eso, y deja la lógica testeable sin montar el shell.
 *
 * Se guarda en memoria a propósito: es una comodidad de la sesión, no algo que
 * merezca ocupar `sessionStorage` ni sobrevivir a un F5.
 */

let posicion = 0;

/** Recuerda dónde quedó el menú. Ignora valores inválidos y negativos. */
export function guardarScrollSidebar(valor: number): void {
  if (!Number.isFinite(valor) || valor < 0) return;
  posicion = valor;
}

/** Dónde estaba el menú la última vez. 0 la primera vez. */
export function scrollSidebarGuardado(): number {
  return posicion;
}

/** Vuelve a cero. Para los tests, y por si alguna vez hay que resetearlo. */
export function olvidarScrollSidebar(): void {
  posicion = 0;
}
