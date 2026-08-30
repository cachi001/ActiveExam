import { useEffect, useState } from 'react';
import { StudentShell } from '../ui/shells';
import { Icon, Button } from '../ui/components';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api, TIPO_EVENTO_LABEL } from '../lib/api';
import type { ExamenContenidoResumen, TipoEvento } from '../lib/types';

function formatFecha(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  // 24 horas y sufijo "hs": es-AR devuelve "06:19 p. m." con espacio duro, que en
  // una fila angosta cortaba el renglón y se leía como un error de la pantalla.
  const fecha = new Intl.DateTimeFormat('es-AR', {
    day: '2-digit', month: 'short', year: 'numeric',
  }).format(d);
  const hora = new Intl.DateTimeFormat('es-AR', {
    hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(d);
  return fecha + ', ' + hora + ' hs';
}

/** Un ÚNICO color para todas las señales.
 *
 * La versión anterior las pintaba por familia (cámara / pantalla / entorno). Tres
 * colores sugieren tres categorías con significados distintos, y el alumno no
 * tiene por qué descifrar qué quiere decir cada tono: son todas lo mismo, cosas
 * que quedan registradas. El color acompaña, no clasifica.
 */
const TONO_SENAL = 'bg-primary-100 text-primary-700';

/** Ícono representativo por tipo de señal registrada (Material Symbols). */
const ICONO_EVENTO: Record<string, string> = {
  rostro_ausente: 'no_accounts',
  multiples_rostros: 'groups',
  mirada_desviada_sostenida: 'visibility',
  perdida_de_foco: 'flip_to_front',
  cambio_pestana: 'tab',
  monitor_adicional: 'devices',
  salida_pantalla_completa: 'fullscreen_exit',
  copiar_pegar: 'content_paste',
  corte_conectividad_prolongado: 'wifi_off',
};

export default function PreExamen() {
  const navigate = useNavigate();
  const examen = useApp((s) => s.examenActivo);
  const [contenido, setContenido] = useState<ExamenContenidoResumen | null>(null);
  // Señales que se registran (detectores activos de la config del sistema).
  const [detectores, setDetectores] = useState<string[]>([]);

  useEffect(() => {
    const id = examen?.examen_contenido_id;
    if (!id) return;
    api.listarExamenesContenido().then((items) => {
      const found = items.find((i) => i.id === id);
      if (found) setContenido(found);
    }).catch(() => {});
  }, [examen?.examen_contenido_id]);

  useEffect(() => {
    api.obtenerConfigEfectiva()
      .then((cfg) => setDetectores(cfg.detectores_activos ?? []))
      .catch(() => {});
  }, []);

  if (!examen) {
    return (
      <StudentShell>
        <div className="flex items-center justify-center min-h-64 text-on-surface-variant">
          Cargando información del examen…
        </div>
      </StudentShell>
    );
  }

  const titulo = contenido?.titulo ?? examen.nombre;
  const materia = contenido?.materia_nombre ?? examen.catedra ?? '—';
  const tiempoLabel = contenido?.tiempo_limite_min
    ? `${contenido.tiempo_limite_min} min`
    : examen.duracion_min
    ? `${examen.duracion_min} min`
    : 'Sin límite';
  const intentosLabel = contenido?.intentos_permitidos ? `${contenido.intentos_permitidos}` : '1';
  // Sin fila de "Preguntas": la cantidad no se le muestra al alumno en ninguna
  // pantalla previa a rendir (decisión del dueño, 28/8/2026).
  //
  // Las dos fechas van en filas SEPARADAS. Antes era una sola fila "Disponible"
  // con las dos pegadas por un guion: en pantallas angostas cortaba en cualquier
  // lado y no se sabía dónde terminaba una y empezaba la otra.
  const ficha = [
    { icon: 'timer', label: 'Tiempo límite', value: tiempoLabel },
    { icon: 'replay', label: 'Intentos permitidos', value: intentosLabel },
    {
      icon: 'event_available',
      label: 'Fecha inicio',
      value: contenido?.apertura ? formatFecha(contenido.apertura) : 'Sin fecha de inicio',
    },
    {
      icon: 'event_busy',
      label: 'Fecha hasta',
      value: contenido?.cierre ? formatFecha(contenido.cierre) : 'Sin fecha de cierre',
    },
  ];

  return (
    <StudentShell backTo="/alumno/mis-examenes">
      <div className="w-full space-y-lg animate-in fade-in duration-300">

        {/* Título. Escala con el ancho: en el tamaño fijo anterior, un título largo
            se comía la pantalla en un notebook chico. */}
        <div className="space-y-xs">
          <p className="text-[11px] uppercase tracking-widest text-primary font-semibold">{materia}</p>
          <h1 className="font-headline text-[20px] sm:text-[24px] leading-tight text-on-surface">
            {titulo}
          </h1>
        </div>

        {/* Dos columnas: ficha + supervisión (izq) · panel de acción (der). Ocupa el ancho. */}
        <div className="grid lg:grid-cols-3 gap-lg items-start">

          {/* Izquierda */}
          <div className="lg:col-span-2 space-y-lg">
            {/* Ficha del examen — tabla simple, estilo institucional */}
            <div className="rounded-2xl border border-outline-variant/50 bg-white overflow-hidden divide-y divide-outline-variant/30">
              {ficha.map((f) => (
                <div
                  key={f.label}
                  className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-3 sm:px-5"
                >
                  <Icon name={f.icon} className="text-on-surface-variant text-[18px] shrink-0" />
                  <span className="text-[13px] text-on-surface-variant flex-1 min-w-[120px]">
                    {f.label}
                  </span>
                  {/* ml-auto + text-right: el valor va a la derecha y, si no entra,
                      baja de renglón en vez de empujar la etiqueta fuera de la fila. */}
                  <span className="text-[13px] sm:text-[14px] font-semibold text-on-surface ml-auto text-right">
                    {f.value}
                  </span>
                </div>
              ))}
            </div>

            {/* Supervisión. Fondo blanco y no lila: el bloque de color competía con
                el panel de acción y hacía ver la pantalla cargada. El color queda
                en los íconos, agrupados por familia, que es lo que ayuda a leer. */}
            <div className="rounded-2xl border border-outline-variant/50 bg-white p-4 sm:p-5 space-y-4">
              <div className="flex items-start gap-3">
                <div className="w-9 h-9 rounded-xl bg-primary-100 text-primary-700 flex items-center justify-center shrink-0">
                  <Icon name="shield_person" className="text-[20px]" />
                </div>
                <div className="min-w-0">
                  <p className="text-[14px] font-semibold text-on-surface">Examen supervisado</p>
                  <p className="text-[13px] text-on-surface-variant mt-0.5 leading-relaxed">
                    Vas a necesitar cámara y pantalla completa. Estas son las señales que
                    quedan registradas para que las revise una persona. El sistema nunca
                    sanciona solo.
                  </p>
                </div>
              </div>
              {detectores.length > 0 && (
                <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-2">
                  {detectores.map((d) => (
                    <div
                      key={d}
                      className="flex items-center gap-2.5 rounded-xl border border-outline-variant/40 bg-surface-50 px-3 py-2.5"
                    >
                      <div className={'w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ' + TONO_SENAL}>
                        <Icon name={ICONO_EVENTO[d] ?? 'visibility'} className="text-[17px]" />
                      </div>
                      <span className="text-[12.5px] font-medium text-on-surface leading-snug">
                        {TIPO_EVENTO_LABEL[d as TipoEvento] ?? d}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Derecha: panel de acción */}
          <aside className="lg:sticky lg:top-6">
            <div className="rounded-2xl border border-outline-variant/50 bg-white p-lg space-y-md text-center">
              <div className="w-12 h-12 rounded-full bg-primary-fixed text-primary flex items-center justify-center mx-auto">
                <Icon name="assignment_turned_in" className="text-[24px]" />
              </div>
              <div className="space-y-xs">
                <p className="text-[16px] font-bold text-on-surface">Todo listo para rendir</p>
                <p className="text-body-sm text-on-surface-variant">
                  {tiempoLabel} · {intentosLabel} {intentosLabel === '1' ? 'intento' : 'intentos'}
                </p>
              </div>
              <Button icon="play_arrow" onClick={() => navigate('/requisitos')} className="w-full">
                Comenzar examen
              </Button>
              <button
                onClick={() => navigate('/alumno/mis-examenes')}
                className="text-label-md text-primary hover:underline w-full"
              >
                Volver
              </button>
              <p className="text-label-xs text-on-surface-variant">
                Una vez que iniciés, el tiempo no se pausa.
              </p>
            </div>
          </aside>

        </div>
      </div>
    </StudentShell>
  );
}
