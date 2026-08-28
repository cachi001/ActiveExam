/**
 * PruebasDelExamenSection — las rendiciones de prueba del docente (migration 0102).
 *
 * Probar el examen antes de soltarlo deja una sesión, y esas sesiones se
 * guardan a propósito: sirven para revisar qué se contestó y cómo se corrigió.
 * Lo que no pueden hacer es contar — no tienen nota, no entran en las
 * estadísticas ni en el envío a Moodle — y se tienen que poder borrar, porque
 * ensayar tres veces no tiene por qué dejar tres sesiones para siempre.
 *
 * La sección no se pinta cuando no hay ninguna: un examen sin ensayos no
 * necesita una tarjeta que diga que no hay ensayos.
 */
import { useEffect, useState } from 'react';
import { Button, Card, Icon, SectionTitle } from '../../ui/components';
import { useToast } from '../../ui/toast';
import { API_BASE } from '../../lib/api';
import { authProvider } from '../../lib/authProvider';
import {
  borrarPruebaDelExamenFn,
  listarPruebasDelExamenFn,
  type PruebaDelExamen,
} from '../../lib/examContentCatalog';

interface Props {
  examenId: string;
}

function cuando(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? '—'
    : d.toLocaleString('es-AR', {
        day: '2-digit',
        month: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      });
}

export function PruebasDelExamenSection({ examenId }: Props) {
  const toast = useToast();
  const [pruebas, setPruebas] = useState<PruebaDelExamen[]>([]);
  const [borrando, setBorrando] = useState<string | null>(null);

  const cargar = () => {
    listarPruebasDelExamenFn(API_BASE, authProvider.getToken(), examenId)
      .then(setPruebas)
      // Silencioso a propósito: es una sección accesoria, y un error acá no
      // tiene por qué tapar el detalle del examen con un toast rojo.
      .catch(() => setPruebas([]));
  };

  useEffect(cargar, [examenId]);

  const borrar = async (sessionId: string) => {
    setBorrando(sessionId);
    try {
      await borrarPruebaDelExamenFn(
        API_BASE,
        authProvider.getToken(),
        examenId,
        sessionId,
      );
      toast.success('Prueba eliminada.');
      cargar();
    } catch (err: unknown) {
      toast.error(
        err instanceof Error ? err.message : 'No se pudo eliminar la prueba.',
      );
    } finally {
      setBorrando(null);
    }
  };

  if (pruebas.length === 0) return null;

  return (
    <Card>
      <SectionTitle
        icon="science"
        sub="Rendiciones que hiciste vos para probar. No cuentan como intentos ni generan nota."
      >
        Pruebas de este examen ({pruebas.length})
      </SectionTitle>

      <div className="rounded-xl border border-outline-variant/40 overflow-hidden">
        {pruebas.map((p, i) => (
          <div
            key={p.session_id}
            className={`flex items-center gap-3 px-4 py-2.5 ${
              i < pruebas.length - 1 ? 'border-b border-outline-variant/20' : ''
            }`}
          >
            <Icon name="science" className="text-[16px] shrink-0 text-on-surface-variant" />
            <div className="flex-1 min-w-0">
              <p className="text-label-md text-on-surface truncate">{p.quien ?? '—'}</p>
              <p className="text-label-sm text-on-surface-variant">
                {cuando(p.creada_en)}
                {p.finalizada_en ? ' · terminada' : ' · sin terminar'}
              </p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              icon="delete"
              onClick={() => borrar(p.session_id)}
              disabled={borrando !== null}
            >
              {borrando === p.session_id ? 'Borrando…' : 'Borrar'}
            </Button>
          </div>
        ))}
      </div>
    </Card>
  );
}
