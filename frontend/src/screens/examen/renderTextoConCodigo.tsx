import type { ReactNode } from 'react';

/**
 * Marcadores invisibles (Unicode Private Use Area) que el backend inserta
 * alrededor de tramos que el autor marcó como código con <code> en Moodle
 * (ver `_strip_html` en moodle_parser.py). Deben coincidir exactamente con
 * `CODE_MARCA_INICIO`/`CODE_MARCA_FIN` del backend.
 */
const CODE_MARCA_INICIO = '';
const CODE_MARCA_FIN = '';

/**
 * Divide un enunciado en tramos de texto normal y tramos de código (marcados
 * por el backend), renderizando el código en monoespaciado sobre un fondo
 * propio para que se distinga claramente de la consigna y de los controles
 * de respuesta — igual que el resaltado que aplica Moodle a sus <code>.
 */
export function renderTextoConCodigo(texto: string, keyPrefix: string): ReactNode[] {
  if (!texto) return [];
  const partes = texto.split(CODE_MARCA_INICIO);
  const nodos: ReactNode[] = [];

  partes.forEach((parte, idx) => {
    if (idx === 0) {
      if (parte) nodos.push(<span key={`${keyPrefix}-t${idx}`}>{parte}</span>);
      return;
    }
    const finIdx = parte.indexOf(CODE_MARCA_FIN);
    if (finIdx === -1) {
      // Marcador de inicio sin cierre (no debería pasar) — tratar todo como texto plano.
      nodos.push(<span key={`${keyPrefix}-t${idx}`}>{parte}</span>);
      return;
    }
    const codigo = parte.slice(0, finIdx);
    const resto = parte.slice(finIdx + CODE_MARCA_FIN.length);
    nodos.push(
      <code
        key={`${keyPrefix}-c${idx}`}
        className="inline-block px-1.5 py-0.5 rounded-md bg-surface-container-high font-mono font-normal text-[0.9em] text-on-surface"
      >
        {codigo}
      </code>,
    );
    if (resto) nodos.push(<span key={`${keyPrefix}-t${idx}`}>{resto}</span>);
  });

  return nodos;
}
