/**
 * Modal para crear un examen desde el banco de preguntas.
 *
 * Flujo:
 *  1. Usuario elige materia y título.
 *  2. El modal carga las categorías del banco para esa materia.
 *  3. Para cada categoría (y "Sin clasificar") el usuario puede poner
 *     cuántas preguntas quiere sortear.
 *  4. Submit → POST /exam-content/crear-desde-banco
 */

import { useEffect, useState } from 'react';
import { Icon, Button, LoadingSpinner } from '../../ui/components';
import { useToast } from '../../ui/toast';
import { api } from '../../lib/api';
import {
  listarCategorias,
  listarPreguntasBanco,
  crearDesdeBanco,
  type CategoriaPregunta,
} from '../../lib/apiAdmin/bancoPreguntasApi';
import type { Materia } from '../../lib/types';

interface TramoSorteo {
  categoria_id: string | null;
  nombre: string;
  disponibles: number;
  cantidad: number;
}

interface Props {
  abierto: boolean;
  onCerrar: () => void;
  onCreado: (examenId: string, totalPreguntas: number) => void;
}

export function CrearExamenModal({ abierto, onCerrar, onCreado }: Props) {
  const toast = useToast();
  const [materias, setMaterias] = useState<Materia[]>([]);
  const [materiaId, setMateriaId] = useState('');
  const [titulo, setTitulo] = useState('');
  const [categorias, setCategorias] = useState<CategoriaPregunta[]>([]);
  const [tramos, setTramos] = useState<TramoSorteo[]>([]);
  const [cargandoCats, setCargandoCats] = useState(false);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    api.materiasDisponibles().then(setMaterias).catch(() => {});
  }, []);

  // Al cambiar materia, cargar categorías + contar disponibles
  useEffect(() => {
    if (!materiaId) {
      setCategorias([]);
      setTramos([]);
      return;
    }
    setCargandoCats(true);
    Promise.all([
      listarCategorias(materiaId),
      listarPreguntasBanco(materiaId, null), // sin clasificar
    ])
      .then(async ([cats, sinClasificar]) => {
        setCategorias(cats);
        const tramosBase: TramoSorteo[] = [];

        // "Sin clasificar" primero
        if (sinClasificar.length > 0) {
          tramosBase.push({
            categoria_id: null,
            nombre: 'Sin clasificar',
            disponibles: sinClasificar.length,
            cantidad: 0,
          });
        }

        // Una por una para obtener conteos (no hay endpoint de count, usamos listar)
        const conConteos = await Promise.all(
          cats.map(async (c) => {
            const preguntas = await listarPreguntasBanco(materiaId, c.id);
            return {
              categoria_id: c.id,
              nombre: c.nombre,
              disponibles: preguntas.length,
              cantidad: 0,
            };
          }),
        );

        tramosBase.push(...conConteos.filter((t) => t.disponibles > 0));
        setTramos(tramosBase);
      })
      .catch(() => toast.error('Error al cargar categorías'))
      .finally(() => setCargandoCats(false));
  }, [materiaId]);

  if (!abierto) return null;

  const setCantidad = (idx: number, val: number) => {
    setTramos((prev) =>
      prev.map((t, i) =>
        i === idx ? { ...t, cantidad: Math.max(0, Math.min(val, t.disponibles)) } : t,
      ),
    );
  };

  const tramosActivos = tramos.filter((t) => t.cantidad > 0);
  const totalPreguntas = tramosActivos.reduce((s, t) => s + t.cantidad, 0);

  const puedeCrear =
    materiaId.trim() !== '' &&
    titulo.trim() !== '' &&
    tramosActivos.length > 0 &&
    !enviando;

  const handleCrear = async () => {
    if (!puedeCrear) return;
    setEnviando(true);
    try {
      const result = await crearDesdeBanco({
        titulo: titulo.trim(),
        materia_id: materiaId,
        sorteo: tramosActivos.map((t) => ({
          categoria_id: t.categoria_id,
          cantidad: t.cantidad,
        })),
      });
      onCreado(result.examen_id, result.total_preguntas);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Error al crear examen');
    } finally {
      setEnviando(false);
    }
  };

  const handleClose = () => {
    if (enviando) return;
    setMateriaId('');
    setTitulo('');
    setTramos([]);
    onCerrar();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40" onClick={handleClose} />
      <div className="relative z-10 w-full max-w-lg bg-white rounded-2xl shadow-xl flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center gap-3 px-6 pt-6 pb-4 border-b border-outline-variant/30">
          <Icon name="quiz" className="text-[22px] text-primary" fill />
          <div className="flex-1">
            <h2 className="text-title-md font-semibold text-on-surface">Crear examen</h2>
            <p className="text-body-sm text-on-surface-variant">
              Sorteá preguntas del banco por categoría
            </p>
          </div>
          <button
            onClick={handleClose}
            className="p-1.5 rounded-lg hover:bg-surface-100 text-on-surface-variant"
          >
            <Icon name="close" className="text-[20px]" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {/* Título */}
          <label className="flex flex-col gap-1">
            <span className="text-label-sm font-medium text-on-surface-variant">
              Título del examen
            </span>
            <input
              type="text"
              value={titulo}
              placeholder="Ej: Parcial 1 — Programación 1"
              onChange={(e) => setTitulo(e.target.value)}
              className="rounded-lg border border-surface-300 px-3 py-2 text-body-sm text-on-surface focus:border-primary focus:outline-none"
            />
          </label>

          {/* Materia */}
          <label className="flex flex-col gap-1">
            <span className="text-label-sm font-medium text-on-surface-variant">Materia</span>
            <select
              value={materiaId}
              onChange={(e) => setMateriaId(e.target.value)}
              className="rounded-lg border border-surface-300 px-3 py-2 text-body-sm text-on-surface focus:border-primary focus:outline-none"
            >
              <option value="">— Seleccioná una materia —</option>
              {materias.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.nombre}
                </option>
              ))}
            </select>
          </label>

          {/* Categorías */}
          {materiaId && (
            <div>
              <p className="text-label-sm font-medium text-on-surface-variant mb-2">
                Preguntas por categoría
              </p>

              {cargandoCats && (
                <LoadingSpinner size="sm" label="Cargando categorías…" />
              )}

              {!cargandoCats && tramos.length === 0 && (
                <p className="text-body-sm text-on-surface-variant italic text-center py-4">
                  No hay preguntas en el banco para esta materia.
                </p>
              )}

              {!cargandoCats && tramos.length > 0 && (
                <div className="rounded-xl border border-outline-variant/40 overflow-hidden">
                  {tramos.map((t, idx) => (
                    <div
                      key={t.categoria_id ?? '__sin_clasificar__'}
                      className={`flex items-center gap-3 px-4 py-2.5 ${
                        idx < tramos.length - 1 ? 'border-b border-outline-variant/20' : ''
                      } ${t.cantidad > 0 ? 'bg-primary/5' : ''}`}
                    >
                      <Icon
                        name={t.categoria_id ? 'folder' : 'inbox'}
                        className={`text-[16px] shrink-0 ${
                          t.cantidad > 0 ? 'text-primary' : 'text-on-surface-variant'
                        }`}
                      />
                      <span
                        className="flex-1 text-body-sm text-on-surface truncate"
                        title={t.nombre}
                      >
                        {t.nombre}
                      </span>
                      <span className="text-label-xs text-on-surface-variant shrink-0">
                        {t.disponibles} disp.
                      </span>
                      <input
                        type="number"
                        min={0}
                        max={t.disponibles}
                        value={t.cantidad || ''}
                        placeholder="0"
                        onChange={(e) =>
                          setCantidad(idx, parseInt(e.target.value, 10) || 0)
                        }
                        className="w-16 rounded-lg border border-surface-300 px-2 py-1 text-body-sm text-right text-on-surface focus:border-primary focus:outline-none"
                      />
                    </div>
                  ))}
                </div>
              )}

              {totalPreguntas > 0 && (
                <p className="text-label-sm text-on-surface-variant mt-2 text-right">
                  Total:{' '}
                  <span className="text-on-surface font-semibold">{totalPreguntas} preguntas</span>
                </p>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-outline-variant/30">
          <Button variant="ghost" onClick={handleClose} disabled={enviando}>
            Cancelar
          </Button>
          <Button
            onClick={handleCrear}
            disabled={!puedeCrear}
            icon={enviando ? undefined : 'shuffle'}
          >
            {enviando ? 'Creando…' : `Crear examen${totalPreguntas > 0 ? ` (${totalPreguntas})` : ''}`}
          </Button>
        </div>
      </div>
    </div>
  );
}
