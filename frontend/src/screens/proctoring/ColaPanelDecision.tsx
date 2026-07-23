/**
 * ColaPanelDecision — Panel de decisión del revisor (C-71 slice 2, D6/D9/D11).
 *
 * UNA decisión, dos salidas: **Aprobar con nota** o **Anular examen**. Ambas
 * exigen MOTIVO (D11); anular exige además la referencia a la evidencia.
 *
 * El backend mantiene el modelo de DOS FASES (revisión → resolución): es lo que
 * da la trazabilidad y permite que mañana resuelva otra autoridad. Pero el
 * revisor no tiene por qué ver esa mecánica: antes la UI la exponía como cuatro
 * botones en dos pasos ("Aprobar con nota / Anular examen", y después "Descartar
 * el caso / Anular la nota por fraude"), pares que decían casi lo mismo — y con
 * el agravante de que "Anular examen" NO anulaba, solo derivaba. Acá las fases se
 * encadenan solas.
 *
 * Quien NO tiene `resolver_caso` (admin, coordinador) ve "Derivar a un revisor"
 * en lugar de anular: ofrecerle anular garantizaba un 403.
 *
 * El sistema solo prioriza y ordena; la decisión es siempre humana, nunca automática.
 * Reusa Card/Button/Icon/SectionTitle/FormField del design system. Sin window.confirm.
 */
import { useState } from 'react';
import { Card, Button, Icon, SectionTitle, FormField } from '../../ui/components';
import type { DecisionRevisor, SesionProctoringResumen } from '../../lib/types';
import type { ExamInfo } from './helpers';
import { scoreTextColor, formatFecha, formatFechaRelativa, modoLabel } from './helpers';

export function ColaPanelDecision({
  sesion,
  info,
  puedeResolver,
  onResolver,
  onVerDetalle,
}: {
  sesion: SesionProctoringResumen;
  info: ExamInfo | null;
  /** Capacidad `resolver_caso` (front-hides; el backend deniega igual). */
  puedeResolver: boolean;
  /** Registra una decisión (fase 1 o 2). Resuelve `true` solo si el backend la confirmó. */
  onResolver: (decision: DecisionRevisor, motivo: string, evidenciaRef?: string) => Promise<boolean>;
  onVerDetalle: () => void;
}) {
  const [motivo, setMotivo] = useState('');
  const [evidenciaRef, setEvidenciaRef] = useState('');
  const [enviando, setEnviando] = useState(false);

  const motivoOk = motivo.trim().length > 0;

  /** Valida la nota. Cierra la revisión sin abrir caso — no hace falta fase 2. */
  const aprobar = async () => {
    if (!motivoOk || enviando) return;
    setEnviando(true);
    await onResolver('aprobado', motivo.trim());
    setEnviando(false);
  };

  /** Deriva sin resolver: única salida para quien no tiene `resolver_caso`. */
  const derivar = async () => {
    if (!motivoOk || enviando) return;
    setEnviando(true);
    await onResolver('caso_abierto', motivo.trim());
    setEnviando(false);
  };

  /**
   * Anula: encadena las DOS fases del backend en un solo acto del revisor.
   *
   * Se abre el caso y, SOLO si el backend lo confirmó, se emite el veredicto.
   * Si la primera falla (409 por decisión ya registrada, 403 sin atribución) no
   * se sigue: emitir un veredicto sobre un caso que nunca se abrió devolvería un
   * 409 y dejaría a la persona sin entender qué pasó.
   */
  const anular = async () => {
    if (!motivoOk || !puedeResolver || enviando) return;
    if (evidenciaRef.trim().length === 0) return;
    setEnviando(true);
    const abierto = await onResolver('caso_abierto', motivo.trim());
    if (abierto) {
      await onResolver('anulado_por_fraude', motivo.trim(), evidenciaRef.trim());
    }
    setEnviando(false);
  };

  return (
    <Card className="space-y-lg">
      <div className="flex items-start justify-between gap-md flex-wrap border-b
        border-outline-variant/40 pb-md">
        <div className="min-w-0">
          <h3 className="font-headline text-title-lg text-on-surface truncate">
            {sesion.etiqueta?.trim() || 'Persona sin etiqueta'}
          </h3>
          {info && (
            <p className="text-label-sm text-on-surface-variant mt-base">
              {info.examNombre} · {info.comisionNombre} · {info.docente}
            </p>
          )}
        </div>
        <span className={`font-headline text-headline-md font-bold ${scoreTextColor(sesion.score)}`}>
          {sesion.score}
        </span>
      </div>

      {/* Resumen del EXPEDIENTE (C-72 backlog #6). Solo datos NO sensibles: métricas
          agregadas + ventana temporal + contexto. Las capturas del alumno (dato
          sensible, Ley 25.326 / regla #7) NO se listan acá: viven solo en el detalle
          completo. El botón de abajo lleva al expediente con la evidencia. */}
      <div className="space-y-sm">
        <div className="grid grid-cols-2 gap-sm">
          <Metrica label="Señales registradas" valor={String(sesion.total_eventos ?? 0)} />
          <Metrica
            label="Diferencias con el servidor"
            valor={String(sesion.total_discrepancias ?? 0)}
            clase={(sesion.total_discrepancias ?? 0) > 0 ? 'text-error' : 'text-on-surface'}
          />
        </div>

        <dl className="rounded-xl bg-white border border-outline-variant/60 p-sm space-y-base text-label-sm">
          <ResumenFila label="Modalidad" valor={modoLabel(sesion.modo)} />
          <ResumenFila label="Inicio" valor={formatFecha(sesion.creada_en)} />
          <ResumenFila
            label={sesion.finalizada_en ? 'Finalizada' : 'Última señal'}
            valor={
              sesion.finalizada_en
                ? formatFecha(sesion.finalizada_en)
                : formatFechaRelativa(sesion.ultimo_evento_en ?? sesion.creada_en)
            }
          />
          <ResumenFila
            label="Estado"
            valor={sesion.finalizada_en ? 'Cerrada' : 'En curso'}
            valorClase={sesion.finalizada_en ? 'text-on-surface-variant' : 'text-primary font-semibold'}
          />
        </dl>
      </div>

      {/* Ver detalle completo — botón real (antes era un link discreto). Lleva al
          expediente con la evidencia sensible (capturas), gated en su propia vista. */}
      <Button
        variant="secondary"
        icon="folder_open"
        iconRight="arrow_forward"
        onClick={onVerDetalle}
        className="w-full justify-center"
      >
        Ver detalle completo
      </Button>

      <div className="border-t border-outline-variant/40 pt-md space-y-md">
        <SectionTitle sub="El sistema solo ordena por prioridad. La decisión es siempre tuya.">
          Decisión del revisor
        </SectionTitle>

        {/* Motivo obligatorio en TODA decisión (D11, RN-RV-06). */}
        <FormField
          label="Motivo (obligatorio)"
          hint="Fundamento de la decisión. Queda en el registro inmutable de auditoría."
          error={!motivoOk ? 'Escribí un motivo para poder registrar la decisión.' : undefined}
        >
          <textarea
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
            rows={2}
            placeholder="Ej.: revisé las 3 señales y corresponden a un falso positivo."
            className="w-full rounded-xl border border-outline-variant/60 bg-white p-sm text-body-md resize-none
              focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
          />
        </FormField>

        {/* Para anular hace falta señalar QUÉ prueba lo fundamenta. Se pide junto
            al motivo y no en un segundo paso: es parte de la misma decisión. */}
        <FormField
          label="Referencia de evidencia (obligatoria para anular)"
          hint="Qué captura o momento fundamenta la anulación. Abrí «Ver detalle completo» para verlas con su fecha y señal."
        >
          <input
            type="text"
            value={evidenciaRef}
            onChange={(e) => setEvidenciaRef(e.target.value)}
            placeholder="Ej.: múltiples rostros, 23/07 11:16"
            className="w-full rounded-xl border border-outline-variant/60 bg-white p-sm text-body-md
              focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
          />
        </FormField>

        {/* UNA sola decisión, dos salidas. Antes eran cuatro botones en dos pasos:
            "Aprobar con nota / Anular examen" y luego "Descartar el caso / Anular la
            nota por fraude" — pares que decían casi lo mismo. Peor: "Anular examen"
            NO anulaba, solo derivaba, y la anulación real estaba en el segundo panel.
            Un botón que promete una cosa y hace otra.
            El modelo de dos fases sigue vivo en el backend (da la trazabilidad y el
            caso de dos autoridades); acá se encadena solo. */}
        <div className="grid gap-sm sm:grid-cols-2">
          <Button
            variant="success"
            icon="verified"
            disabled={!motivoOk || enviando}
            onClick={() => aprobar()}
            className="justify-center"
          >
            Aprobar con nota
          </Button>
          {puedeResolver ? (
            <Button
              variant="danger"
              icon="gavel"
              disabled={!motivoOk || enviando || evidenciaRef.trim().length === 0}
              onClick={() => anular()}
              className="justify-center font-bold ring-2 ring-error/30"
            >
              Anular examen
            </Button>
          ) : (
            // Sin `resolver_caso` no se puede emitir el veredicto: lo único
            // disponible es derivar. Mostrar "Anular examen" a quien no puede
            // anular garantiza un 403 y una persona confundida.
            <Button
              variant="outline"
              icon="forward_to_inbox"
              disabled={!motivoOk || enviando}
              onClick={() => derivar()}
              className="justify-center"
            >
              Derivar a un revisor
            </Button>
          )}
        </div>

        {!puedeResolver && (
          <p className="text-label-sm text-on-surface-variant inline-flex items-center gap-base">
            <Icon name="lock" className="text-[16px]" />
            No tenés la atribución para anular. Podés aprobar la nota o derivar el caso
            a quien sí la tenga.
          </p>
        )}
      </div>
    </Card>
  );
}

function Metrica({
  label,
  valor,
  clase = 'text-on-surface',
}: {
  label: string;
  valor: string;
  clase?: string;
}) {
  return (
    <div className="rounded-xl bg-white border border-outline-variant/60 p-sm">
      <p className="text-label-sm uppercase tracking-wide text-on-surface-variant">{label}</p>
      <p className={`font-headline text-title-lg font-bold ${clase}`}>{valor}</p>
    </div>
  );
}

/** Fila etiqueta→valor del resumen del expediente (dato no sensible). */
function ResumenFila({
  label,
  valor,
  valorClase = 'text-on-surface',
}: {
  label: string;
  valor: string;
  valorClase?: string;
}) {
  return (
    <div className="flex items-center justify-between gap-md">
      <dt className="text-on-surface-variant">{label}</dt>
      <dd className={`font-medium text-right truncate ${valorClase}`}>{valor}</dd>
    </div>
  );
}

export default ColaPanelDecision;
