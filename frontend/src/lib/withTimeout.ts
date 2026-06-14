/**
 * withTimeout — corre una promesa contra un límite de tiempo (C-67 fix).
 *
 * Si `promise` settlea (resuelve o rechaza) antes de `ms`, se propaga tal cual.
 * Si no, la promesa devuelta RECHAZA con un Error de timeout — para que el caller
 * pueda degradar (p. ej. ofrecer el modo manual) en vez de quedar colgado para
 * siempre. Usado para blindar la carga del motor de visión en el teléfono, donde
 * la descarga de los modelos (WASM ~11 MB) sobre el túnel puede stallar.
 *
 * Limpia el timer en cualquier caso para no dejar handles colgando.
 */
export function withTimeout<T>(
  promise: Promise<T>,
  ms: number,
  message = "La operación tardó demasiado",
): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new Error(message));
    }, ms);

    promise.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (err) => {
        clearTimeout(timer);
        reject(err);
      },
    );
  });
}
