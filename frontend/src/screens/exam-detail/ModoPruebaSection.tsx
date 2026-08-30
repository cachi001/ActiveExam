/**
 * ModoPruebaSection — ensayar el examen antes de tomarlo (migración 0105).
 *
 * Mientras el modo prueba está prendido, el examen es un ensayo: solo lo ven los
 * alumnos habilitados acá, y nada de lo que rindan cuenta (no genera nota, no va
 * al campus, no entra a la cola de revisión ni a las estadísticas, y las sesiones
 * se pueden borrar).
 *
 * Por qué la lista es explícita y no la comisión entera: un ensayo no le tiene
 * que aparecer a las 70 personas que van a rendir el examen de verdad.
 *
 * Para elegir a quién habilitar hay un BUSCADOR, no un campo de identificador.
 * La primera versión pedía pegar el id interno del alumno: nadie lo sabe de
 * memoria, hay que ir a buscarlo a otra pantalla y copiarlo, y un carácter de
 * más devuelve un error incomprensible. Se busca por nombre o usuario, que es lo
 * que el docente sí conoce.
 */
import { useEffect, useRef, useState } from 'react';
import { Button, Card, Icon } from '../../ui/components';
import { useToast } from '../../ui/toast';
import { API_BASE } from '../../lib/api';
import { authProvider } from '../../lib/authProvider';
import { usuariosApi } from '../../lib/apiAdmin/usuarios';
import {
  cambiarModoPruebaFn,
  listarHabilitadosPruebaFn,
  habilitarAlumnoPruebaFn,
  quitarAlumnoPruebaFn,
  type AlumnoHabilitadoPrueba,
} from '../../lib/examContentCatalog';

interface Props {
  examenId: string;
  modoPrueba: boolean;
  onCambio: () => void;
}

interface AlumnoBuscado {
  id: string;
  username: string;
  nombre: string;
}

export function ModoPruebaSection({ examenId, modoPrueba, onCambio }: Props) {
  const toast = useToast();
  const [habilitados, setHabilitados] = useState<AlumnoHabilitadoPrueba[]>([]);
  const [busqueda, setBusqueda] = useState('');
  const [resultados, setResultados] = useState<AlumnoBuscado[]>([]);
  const [buscando, setBuscando] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const debounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cargar = () => {
    listarHabilitadosPruebaFn(API_BASE, authProvider.getToken(), examenId)
      .then(setHabilitados)
      .catch(() => setHabilitados([]));
  };

  useEffect(cargar, [examenId]);

  // Búsqueda con freno de 300 ms: sin esto se dispara un pedido por tecla.
  useEffect(() => {
    if (!modoPrueba) return;
    if (debounce.current) clearTimeout(debounce.current);
    debounce.current = setTimeout(() => {
      setBuscando(true);
      usuariosApi
        .listarUsuarios(8, 0, { rol: 'estudiante', estado: 'activo', q: busqueda || undefined })
        .then((r) => {
          const items = (r.items ?? []) as Array<{
            id: string;
            username: string;
            nombre?: string | null;
            apellido?: string | null;
          }>;
          setResultados(
            items.map((u) => ({
              id: u.id,
              username: u.username,
              nombre: `${u.nombre ?? ''} ${u.apellido ?? ''}`.trim() || u.username,
            })),
          );
        })
        .catch(() => setResultados([]))
        .finally(() => setBuscando(false));
    }, 300);
    return () => {
      if (debounce.current) clearTimeout(debounce.current);
    };
  }, [busqueda, modoPrueba]);

  const alternar = async () => {
    setGuardando(true);
    try {
      await cambiarModoPruebaFn(API_BASE, authProvider.getToken(), examenId, !modoPrueba);
      toast.success(
        modoPrueba
          ? 'Modo prueba apagado. El examen vuelve a ser real.'
          : 'Modo prueba prendido. Lo que se rinda no va a contar.',
      );
      onCambio();
    } catch (e) {
      toast.warning(e instanceof Error ? e.message : 'No se pudo cambiar el modo prueba.');
    } finally {
      setGuardando(false);
    }
  };

  const habilitar = async (alumno: AlumnoBuscado) => {
    setGuardando(true);
    try {
      await habilitarAlumnoPruebaFn(API_BASE, authProvider.getToken(), examenId, alumno.id);
      setBusqueda('');
      cargar();
      toast.success(`${alumno.nombre} ya puede ver el examen de prueba.`);
    } catch (e) {
      toast.warning(e instanceof Error ? e.message : 'No se pudo habilitar.');
    } finally {
      setGuardando(false);
    }
  };

  const quitar = async (id: string) => {
    setGuardando(true);
    try {
      await quitarAlumnoPruebaFn(API_BASE, authProvider.getToken(), examenId, id);
      cargar();
    } catch (e) {
      toast.warning(e instanceof Error ? e.message : 'No se pudo quitar de la lista.');
    } finally {
      setGuardando(false);
    }
  };

  const yaHabilitados = new Set(habilitados.map((h) => h.usuario_id));
  const sugerencias = resultados.filter((r) => !yaHabilitados.has(r.id));

  return (
    <Card className="p-0 overflow-hidden">
      {/* Cabecera con el estado bien visible: prendido o apagado es lo primero
          que hay que poder leer, sin buscar dentro de un párrafo. */}
      <div
        className={`flex flex-wrap items-center justify-between gap-3 px-5 py-4 border-b ${
          modoPrueba
            ? 'bg-warning-100 border-warning-300'
            : 'bg-surface-50 border-surface-200'
        }`}
      >
        <div className="flex items-center gap-3 min-w-0">
          <div
            className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
              modoPrueba ? 'bg-warning-200 text-warning-800' : 'bg-surface-200 text-on-surface-variant'
            }`}
          >
            <Icon name="science" className="text-[20px]" />
          </div>
          <div className="min-w-0">
            <p className="text-[15px] font-semibold text-on-surface">
              {modoPrueba ? 'Modo prueba prendido' : 'Modo prueba'}
            </p>
            <p className="text-[12.5px] text-on-surface-variant mt-0.5">
              {modoPrueba
                ? 'Es un ensayo: lo ven solo las personas de la lista.'
                : 'Para ensayar el examen antes de tomarlo.'}
            </p>
          </div>
        </div>
        <Button
          variant={modoPrueba ? 'warning' : 'primary'}
          size="sm"
          icon={modoPrueba ? 'stop_circle' : 'play_arrow'}
          onClick={alternar}
          disabled={guardando}
        >
          {modoPrueba ? 'Apagar' : 'Prender'}
        </Button>
      </div>

      <div className="px-5 py-4">
        {!modoPrueba ? (
          <p className="text-[13px] text-on-surface-variant">
            Prendelo para que alguien lo rinda antes que la comisión. Esas rendiciones
            no generan nota, no van al campus y se pueden borrar después.
          </p>
        ) : (
          <>
            {/* Las tres consecuencias, como datos y no como párrafo: es lo que el
                docente necesita confirmar antes de dejar rendir a alguien. */}
            <ul className="mb-4 grid gap-1.5 sm:grid-cols-3">
              {[
                ['block', 'No generan nota'],
                ['cloud_off', 'No van al campus'],
                ['delete_sweep', 'Se pueden borrar'],
              ].map(([icono, texto]) => (
                <li
                  key={texto}
                  className="flex items-center gap-2 rounded-lg bg-surface-50 px-3 py-2 text-[12.5px] text-on-surface-variant"
                >
                  <Icon name={icono} className="text-[16px] text-on-surface-variant/70" />
                  {texto}
                </li>
              ))}
            </ul>

            <p className="text-[13px] font-medium text-on-surface">Quién puede verlo</p>
            <p className="mt-0.5 text-[12.5px] text-on-surface-variant">
              Buscá por nombre o usuario. Solo aparecen cuentas de estudiante.
            </p>

            <div className="relative mt-2">
              <Icon
                name="search"
                className="absolute left-3 top-1/2 -translate-y-1/2 text-[18px] text-on-surface-variant/60 pointer-events-none"
              />
              <input
                type="text"
                value={busqueda}
                onChange={(e) => setBusqueda(e.target.value)}
                placeholder="Buscar alumno…"
                disabled={guardando}
                className="w-full rounded-lg border border-surface-300 bg-white pl-10 pr-3 py-2.5 text-[13px] text-on-surface focus:border-primary focus:outline-none disabled:opacity-50"
              />
            </div>

            {/* Resultados: se muestran siempre que haya, no detrás de un botón.
                Habilitar es un click sobre la persona, no copiar un id. */}
            {sugerencias.length > 0 && (
              <ul className="mt-2 rounded-lg border border-surface-200 divide-y divide-surface-200 overflow-hidden">
                {sugerencias.map((a) => (
                  <li key={a.id}>
                    <button
                      type="button"
                      onClick={() => habilitar(a)}
                      disabled={guardando}
                      className="w-full flex items-center gap-3 px-3 py-2.5 text-left hover:bg-primary-50 disabled:opacity-50"
                    >
                      <span className="w-7 h-7 rounded-full bg-primary-100 text-primary-700 text-[12px] font-semibold flex items-center justify-center shrink-0">
                        {a.nombre.slice(0, 1).toUpperCase()}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-[13px] text-on-surface truncate">{a.nombre}</span>
                        <span className="block text-[12px] text-on-surface-variant truncate">
                          {a.username}
                        </span>
                      </span>
                      <Icon name="add" className="text-[18px] text-primary shrink-0" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {!buscando && busqueda && sugerencias.length === 0 && (
              <p className="mt-2 text-[12.5px] text-on-surface-variant">
                Ningún alumno coincide con «{busqueda}».
              </p>
            )}

            <div className="mt-4">
              <p className="text-[12.5px] font-medium text-on-surface-variant">
                Habilitados ({habilitados.length})
              </p>
              {habilitados.length === 0 ? (
                <p className="mt-1 text-[12.5px] text-on-surface-variant">
                  Todavía no habilitaste a nadie: por ahora no lo ve ningún alumno.
                </p>
              ) : (
                <ul className="mt-2 flex flex-wrap gap-2">
                  {habilitados.map((a) => (
                    <li
                      key={a.usuario_id}
                      className="inline-flex items-center gap-2 rounded-full border border-surface-300 bg-surface-50 pl-3 pr-1.5 py-1"
                    >
                      <span className="text-[12.5px] text-on-surface">{a.nombre}</span>
                      <button
                        type="button"
                        onClick={() => quitar(a.usuario_id)}
                        disabled={guardando}
                        aria-label={`Quitar a ${a.nombre}`}
                        className="w-5 h-5 rounded-full flex items-center justify-center text-on-surface-variant hover:bg-surface-200 hover:text-on-surface disabled:opacity-50"
                      >
                        <Icon name="close" className="text-[14px]" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </>
        )}
      </div>
    </Card>
  );
}
