/**
 * BorradorSection — habilitar un examen que todavía está en borrador (c-78 E-07).
 *
 * Un examen en borrador no le aparece al alumno y no lo puede rendir, ni siquiera
 * con la URL guardada (el corte es server-side, en el enforcement). El docente sí
 * lo puede rendir entero, incluso antes de la fecha de apertura, que es justo
 * cuando tiene sentido probarlo.
 *
 * Habilitar se puede deshacer MIENTRAS NADIE lo haya rendido: un click
 * equivocado no tiene por qué ser irreversible. Desde el primer intento ya no,
 * porque esconderlo le sacaría el examen de abajo a quien está en el medio; ahí
 * el camino es la baja lógica, que conserva la evidencia de lo rendido.
 */
import { useState } from 'react';
import { Button, Card, Icon, SectionTitle } from '../../ui/components';
import { ConfirmModal } from '../../ui/ConfirmModal';
import { useToast } from '../../ui/toast';
import { API_BASE } from '../../lib/api';
import { authProvider } from '../../lib/authProvider';
import {
  habilitarExamenFn,
  volverExamenABorradorFn,
} from '../../lib/examContentCatalog';

interface Props {
  examenId: string;
  titulo: string | undefined;
  /** Si el examen está sin habilitar. Cambia la sección entera. */
  borrador: boolean;
  /** Se llama tras habilitar o esconder, para refrescar el encabezado. */
  onHabilitado: () => void;
}

export function BorradorSection({ examenId, titulo, borrador, onHabilitado }: Props) {
  const toast = useToast();
  const [confirmando, setConfirmando] = useState(false);
  const [escondiendo, setEscondiendo] = useState(false);
  const [enviando, setEnviando] = useState(false);

  const volverABorrador = async () => {
    setEscondiendo(false);
    setEnviando(true);
    try {
      await volverExamenABorradorFn(API_BASE, authProvider.getToken(), examenId);
      toast.success('El examen volvió a borrador. Los alumnos dejaron de verlo.');
      onHabilitado();
    } catch (err: unknown) {
      // El 409 llega con el detalle de cuántos lo rindieron: se muestra tal cual
      // en vez de un "no se pudo" que obligaría a adivinar el motivo.
      toast.error(
        err instanceof Error
          ? err.message
          : 'No se pudo devolver el examen a borrador.',
      );
    } finally {
      setEnviando(false);
    }
  };

  const habilitar = async () => {
    setConfirmando(false);
    setEnviando(true);
    try {
      await habilitarExamenFn(API_BASE, authProvider.getToken(), examenId);
      toast.success('El examen quedó habilitado. Los alumnos ya lo pueden rendir.');
      onHabilitado();
    } catch (err: unknown) {
      toast.error(
        err instanceof Error ? err.message : 'No se pudo habilitar el examen.',
      );
    } finally {
      setEnviando(false);
    }
  };

  if (!borrador) {
    return (
      <Card>
        <SectionTitle
          icon="visibility"
          sub="Los alumnos de su comisión lo pueden rendir en la ventana configurada."
        >
          Habilitado
        </SectionTitle>
        <div className="flex items-start justify-between gap-4">
          <p className="text-label-sm text-on-surface-variant">
            Se puede volver a esconder mientras no lo haya rendido nadie. Después de
            eso, para sacarlo de circulación hay que darlo de baja.
          </p>
          <Button
            variant="secondary"
            size="sm"
            icon={enviando ? undefined : 'visibility_off'}
            onClick={() => setEscondiendo(true)}
            disabled={enviando}
          >
            {enviando ? 'Guardando…' : 'Volver a borrador'}
          </Button>
        </div>

        <ConfirmModal
          abierto={escondiendo}
          titulo="Volver a borrador"
          textoConfirmar="Volver a borrador"
          mensaje={
            <p>
              «{titulo}» deja de aparecerle a los alumnos y no lo van a poder rendir
              hasta que lo habilites de nuevo. Si alguno ya lo rindió, no se va a
              poder y te vamos a decir cuántos son.
            </p>
          }
          onConfirmar={volverABorrador}
          onCancelar={() => setEscondiendo(false)}
        />
      </Card>
    );
  }

  return (
    <Card>
      <SectionTitle
        icon="visibility_off"
        sub="Este examen todavía no está disponible para los alumnos."
      >
        Sin habilitar
      </SectionTitle>

      <div className="space-y-4">
        <div className="rounded-xl border border-warning/40 bg-warning-container/30 px-4 py-3">
          <p className="text-label-md text-on-surface">
            A los alumnos no les aparece en su lista y no lo pueden rendir, aunque tengan
            el link.
          </p>
          {/* Antes acá decía "Vos sí lo podés rendir para ver cómo queda de punta a
              punta". No era cierto: el enforcement le saltea el borrador y la ventana
              al docente, pero después la guarda de inscripción lo frena con 403
              ("No estás inscripto en la comisión"), y un docente nunca está inscripto
              como alumno de su propia comisión. Prometer algo que la aplicación
              rechaza es peor que no ofrecerlo. Lo que SÍ puede hacer es revisar el
              contenido, que es para lo que se usa el borrador. */}
          <p className="text-label-md text-on-surface-variant mt-2">
            Mientras tanto podés revisarlo: más abajo están{' '}
            <strong>todas las preguntas del examen</strong>, con los huecos como los ve
            el alumno, y la configuración de fechas, intentos y escala de nota.
          </p>
        </div>

        <div className="flex items-start gap-2 text-label-sm text-on-surface-variant">
          <Icon name="info" className="text-[18px] shrink-0 mt-0.5" />
          <p>
            Lo podés volver a esconder mientras no lo rinda nadie. Desde el primer
            alumno que entre ya no, porque le sacaría el examen de abajo: ahí el
            camino es dar de baja el examen, que conserva lo rendido.
          </p>
        </div>

        <div className="flex justify-end">
          <Button
            variant="primary"
            size="sm"
            icon={enviando ? undefined : 'visibility'}
            onClick={() => setConfirmando(true)}
            disabled={enviando}
          >
            {enviando ? 'Habilitando…' : 'Habilitar para los alumnos'}
          </Button>
        </div>
      </div>

      <ConfirmModal
        abierto={confirmando}
        titulo="Habilitar el examen"
        textoConfirmar="Habilitar"
        mensaje={
          <>
            <p>
              «{titulo}» pasa a estar disponible para los alumnos de su comisión, dentro
              de la ventana de rendición configurada.
            </p>
            <p className="mt-2">
              Revisá que las preguntas, la fecha y la escala de nota estén como querés.
              Si te arrepentís, lo podés volver a borrador mientras no lo haya rendido
              nadie.
            </p>
          </>
        }
        onConfirmar={habilitar}
        onCancelar={() => setConfirmando(false)}
      />
    </Card>
  );
}
