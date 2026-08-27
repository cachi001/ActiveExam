// Qué se ve por encima de qué. Escala ÚNICA de la interfaz.
//
// Había diez valores distintos de z-index para overlays (30, 40, 50, 60, 90, 95,
// 100, 110, 200, 1000), elegidos a ojo uno por uno. Con esa dispersión es cuestión
// de tiempo que un diálogo nuevo caiga por debajo del marco: pasó con cuatro
// modales en `z-50`, empatados con el header, que oscurecían el contenido y dejaban
// la sidebar y la barra superior iluminadas por encima.
//
// Los saltos son de 100 a propósito: dejan lugar para acomodar algo entre dos capas
// sin tener que renumerar las de arriba.
export const CAPAS = {
  /** Backdrop del menú lateral en mobile. Por debajo de la sidebar que oscurece. */
  backdropSidebar: 30,
  /** Menú lateral fijo. */
  sidebar: 40,
  /** Barra superior fija. Todo modal tiene que estar POR ENCIMA de esto. */
  header: 50,
  /** Menús contextuales anclados a un botón (kebab, desplegables del header). */
  menu: 60,
  /** Overlays del examen en curso (lockdown, pausa, calibración). El alumno rinde
   *  sin sidebar ni header, así que solo se apilan entre ellos. */
  examen: 95,
  /** Diálogos y modales sobre el shell de staff. */
  modal: 100,
  /** Contenido que se abre DESDE un modal (una captura ampliada, por ejemplo). */
  sobreModal: 110,
  /** Paneles de ayuda y glosario: se consultan con un modal abierto. */
  ayuda: 200,
  /** Avisos. Van arriba de todo: un "no se pudo guardar" tapado por el diálogo que
   *  lo provocó es un aviso que nadie lee. */
  toast: 300,
} as const;

export type Capa = keyof typeof CAPAS;

export default CAPAS;
