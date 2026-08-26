/**
 * BorradorSection — habilitar un examen que todavía está en borrador (c-78 E-07).
 *
 * Un examen en borrador no le aparece al alumno y no lo puede rendir, ni siquiera
 * con la URL guardada (el corte es server-side, en el enforcement). El docente sí
 * lo puede rendir entero, incluso antes de la fecha de apertura, que es justo
 * cuando tiene sentido probarlo.
 *
 * Habilitar es de IDA: para sacarlo de circulación después está la baja lógica,
 * que es explícita y conserva la evidencia de lo ya rendido.
 */
import { useState } from 'react';
import { Button, Card, Icon, SectionTitle } from '../../ui/components';
import { ConfirmModal } from '../../ui/ConfirmModal';
import { useToast } from '../../ui/toast';
import { API_BASE } from '../../lib/api';
import { authProvider } from '../../lib/authProvider';
import { habilitarExamenFn } from '../../lib/examContentCatalog';

interface Props {
  examenId: string;
  titulo: string | undefined;
  /** Se llama tras habilitar, para que la pantalla refresque el encabezado. */
  onHabilitado: () => void;
}

export function BorradorSection({ examenId, titulo, onHabilitado }: Props) {
  const toast = useToast();
  const [confirmando, setConfirmando] = useState(false);
  const [enviando, setEnviando] = useState(false);

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
          <p className="text-label-md text-on-surface-variant mt-2">
            <strong>Vos sí lo podés rendir</strong> para ver cómo queda de punta a punta,
            incluso antes de la fecha de apertura. Ese intento es de prueba y no cuenta
            como una rendición real.
          </p>
        </div>

        <div className="flex items-start gap-2 text-label-sm text-on-surface-variant">
          <Icon name="info" className="text-[18px] shrink-0 mt-0.5" />
          <p>
            Habilitarlo es un camino de ida. Si después necesitás sacarlo de circulación,
            se hace dando de baja el examen, que conserva todo lo que se haya rendido.
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
              Es un camino de ida: no se puede volver a poner en borrador. Revisá que las
              preguntas, la fecha y la escala de nota estén como querés.
            </p>
          </>
        }
        onConfirmar={habilitar}
        onCancelar={() => setConfirmando(false)}
      />
    </Card>
  );
}
