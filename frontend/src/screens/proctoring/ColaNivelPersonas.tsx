/**
 * ColaNivelPersonas — Nivel hoja del drill-down: las personas (sesiones de proctoring)
 * en riesgo de un examen puntual. Tabla (no cards): con volumen (10+ personas) una
 * grilla de cards se vuelve abrumadora para escanear y comparar score/señales entre
 * filas; la tabla alinea las columnas y se lee de un vistazo. Un click ABRE EL CASO
 * en el detalle completo: la lista es para elegir a quién revisar, el expediente
 * para decidir (la decisión es inmutable y exige mirar la evidencia, cosa que un
 * panel lateral angosto no permite).
 */
import { Card, Badge, Icon, SectionTitle } from '../../ui/components';
import { AdminTable, type AdminColumn } from '../../ui/AdminTable';
import { formatFechaRelativa } from './helpers';
import type { SesionEnriquecida } from './colaAgregacion';

export function ColaNivelPersonas({
  personas,
  selId,
  onSeleccionar,
}: {
  personas: SesionEnriquecida[];
  /** Solo resalta la fila abierta al volver del detalle. */
  selId: string | null;
  /** Abre el caso en el expediente, donde se decide. */
  onSeleccionar: (id: string) => void;
}) {
  const columns: AdminColumn<SesionEnriquecida>[] = [
    {
      key: 'persona',
      header: 'Persona',
      width: '32%',
      cell: (item) => (
        <span className={`inline-flex items-center gap-1.5 font-medium ${
          selId === item.sesion.id ? 'text-primary' : 'text-surface-900'
        }`}>
          {selId === item.sesion.id && <Icon name="chevron_right" className="text-[16px] shrink-0" />}
          {item.sesion.etiqueta?.trim() || 'Persona sin etiqueta'}
        </span>
      ),
    },
    {
      key: 'score',
      header: 'Riesgo',
      width: '14%',
      cell: (item) => <Badge tone="error">{item.sesion.score} pts</Badge>,
    },
    {
      key: 'senales',
      header: 'Señales',
      width: '16%',
      cell: (item) => (
        <span className="inline-flex items-center gap-1 text-surface-600">
          <Icon name="sensors" className="text-[15px] text-surface-400" />
          {item.sesion.total_eventos ?? 0}
        </span>
      ),
    },
    {
      key: 'diferencias',
      header: 'Diferencias',
      width: '16%',
      cell: (item) => (
        <span
          className={`inline-flex items-center gap-1 ${
            (item.sesion.total_discrepancias ?? 0) > 0 ? 'text-error font-medium' : 'text-surface-600'
          }`}
        >
          <Icon name="difference" className="text-[15px]" />
          {item.sesion.total_discrepancias ?? 0}
        </span>
      ),
    },
    {
      key: 'fecha',
      header: 'Cuándo',
      width: '22%',
      cell: (item) => (
        <span className="inline-flex items-center gap-1 text-surface-500">
          <Icon name="schedule" className="text-[15px] text-surface-400" />
          {formatFechaRelativa(item.sesion.creada_en)}
        </span>
      ),
    },
  ];

  return (
    <section className="space-y-md">
      <SectionTitle
        sub="Cada persona en riesgo de este examen. Elegí una fila para revisar y decidir."
        action={
          <Badge tone="error" dot>
            {personas.length} en riesgo
          </Badge>
        }
      >
        Personas en riesgo
      </SectionTitle>

      {personas.length === 0 ? (
        <Card className="text-center py-xl space-y-base">
          <Icon name="task_alt" className="text-success text-[40px]" fill />
          <p className="text-label-md text-on-surface-variant">
            No quedan personas en riesgo en este examen.
          </p>
        </Card>
      ) : (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
          <AdminTable
            columns={columns}
            data={personas}
            keyExtractor={(item) => item.sesion.id}
            onRowClick={(item) => onSeleccionar(item.sesion.id)}
            tableMinWidth="640px"
          />
        </div>
      )}
    </section>
  );
}

export default ColaNivelPersonas;
