/**
 * ModalOverlay — el fondo oscuro de cualquier diálogo a pantalla completa.
 *
 * ## Por qué existe
 *
 * Los modales que se escribían a mano como `<div class="fixed inset-0 z-... bg-black/60">`
 * quedaban DEBAJO del header y de la sidebar: oscurecían el contenido y dejaban el
 * marco iluminado, como si el diálogo estuviera atrás de la aplicación.
 *
 * No es el z-index. Medido en el navegador el 27/8/2026, un overlay con z-200
 * perdía contra un header de z-50. La causa es el contexto de apilamiento: las
 * pantallas se envuelven en `animate-in fade-in`, animación sobre `opacity` con
 * `animation-fill-mode: both`, y eso crea un contexto de apilamiento permanente en
 * el contenedor de la página. Un `position: fixed` declarado adentro deja de
 * compararse con el header y pasa a apilarse dentro de ese contexto, que se pinta
 * donde le toca al contenido. El z-index del modal deja de tener efecto sobre el
 * marco por más alto que sea.
 *
 * La cura es montar el overlay en `document.body` con un portal: ahí vuelve al
 * contexto raíz y su z-index compite de nuevo con el header.
 *
 * Además unifica el backdrop. Llegó a haber cinco variantes a ojo (`/30`, `/40`,
 * `/50`, `/70`, una sola con blur): con negro al 40% y sin desenfoque, la sidebar
 * blanca se sigue leyendo nítida y el ojo la toma como primer plano aunque esté
 * correctamente tapada.
 *
 * `ui/capas.test.ts` falla si aparece un modal nuevo que no pase por acá.
 */
import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { CAPAS } from './capas';

export function ModalOverlay({
  etiqueta,
  onCerrar,
  children,
  className = '',
}: {
  /** Qué es este diálogo, para lectores de pantalla. */
  etiqueta: string;
  /** Cierre con Escape y con click en el fondo. Omitirlo hace el modal obligatorio
   *  (una captura biométrica en curso, por ejemplo, que no se abandona a medias). */
  onCerrar?: () => void;
  children: React.ReactNode;
  className?: string;
}) {
  useEffect(() => {
    if (!onCerrar) return;
    const alTeclado = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCerrar();
    };
    document.addEventListener('keydown', alTeclado);
    return () => document.removeEventListener('keydown', alTeclado);
  }, [onCerrar]);

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-label={etiqueta}
      style={{ zIndex: CAPAS.modal }}
      className={`fixed inset-0 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 ${className}`}
      onClick={onCerrar ? () => onCerrar() : undefined}
    >
      {/* El click de adentro no cierra: si no, cualquier click en el formulario
          descartaría lo que la persona está cargando. */}
      <div className="contents" onClick={(e) => e.stopPropagation()}>
        {children}
      </div>
    </div>,
    document.body,
  );
}

export default ModalOverlay;
