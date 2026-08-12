import { useState } from 'react';
import { Icon, Button } from '../../ui/components';
import type { CategoriaPregunta } from '../../lib/apiAdmin/bancoPreguntasApi';

interface NodoArbol extends CategoriaPregunta {
  hijos: NodoArbol[];
}

// Canal de datos del drag&drop del banco. Una categoría se arrastra para
// re-anidarla; una pregunta (desde la lista) se suelta sobre una categoría
// para moverla ahí. El MIME custom evita colisionar con drags del navegador.
const DND_MIME = 'application/x-banco';
type DndPayload = { kind: 'category' | 'question'; id: string };

export function serializarDnd(payload: DndPayload): string {
  return JSON.stringify(payload);
}
function leerDnd(e: React.DragEvent): DndPayload | null {
  const raw = e.dataTransfer.getData(DND_MIME);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as DndPayload;
  } catch {
    return null;
  }
}

function buildTree(cats: CategoriaPregunta[]): NodoArbol[] {
  const byId = new Map<string, NodoArbol>();
  cats.forEach((c) => byId.set(c.id, { ...c, hijos: [] }));
  const raices: NodoArbol[] = [];
  byId.forEach((nodo) => {
    if (nodo.categoria_padre_id && byId.has(nodo.categoria_padre_id)) {
      byId.get(nodo.categoria_padre_id)!.hijos.push(nodo);
    } else {
      raices.push(nodo);
    }
  });
  return raices;
}

interface Props {
  categorias: CategoriaPregunta[];
  seleccionada: string | null;
  /** Cuántas preguntas hay sin clasificar. El bucket solo se muestra si es > 0. */
  sinClasificarCount: number;
  onSeleccionar: (id: string | null) => void;
  onCrear: (padreId: string | null) => void;
  onRenombrar: (cat: CategoriaPregunta) => void;
  onBorrar: (cat: CategoriaPregunta) => void;
  /** Re-anidar una categoría (drag&drop). Si falta, el árbol no es arrastrable. */
  onMoverCategoria?: (categoriaId: string, nuevoPadreId: string | null) => void;
  /** Soltar una pregunta sobre una categoría (o "sin clasificar" con null). */
  onMoverPregunta?: (preguntaId: string, categoriaId: string | null) => void;
}

function NodoCategoria({
  nodo,
  nivel,
  seleccionada,
  dndActivo,
  onSeleccionar,
  onCrear,
  onRenombrar,
  onBorrar,
  onMoverCategoria,
  onMoverPregunta,
}: {
  nodo: NodoArbol;
  nivel: number;
  seleccionada: string | null;
  dndActivo: boolean;
  onSeleccionar: (id: string | null) => void;
  onCrear: (padreId: string | null) => void;
  onRenombrar: (cat: CategoriaPregunta) => void;
  onBorrar: (cat: CategoriaPregunta) => void;
  onMoverCategoria?: (categoriaId: string, nuevoPadreId: string | null) => void;
  onMoverPregunta?: (preguntaId: string, categoriaId: string | null) => void;
}) {
  const [expandido, setExpandido] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const activo = seleccionada === nodo.id;

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
    const payload = leerDnd(e);
    if (!payload) return;
    if (payload.kind === 'category' && payload.id !== nodo.id) {
      onMoverCategoria?.(payload.id, nodo.id);
    } else if (payload.kind === 'question') {
      onMoverPregunta?.(payload.id, nodo.id);
    }
  }

  return (
    <div style={{ paddingLeft: nivel * 16 }}>
      <div
        className={`flex items-center gap-2 px-2 py-2 rounded-lg cursor-pointer group transition-all duration-150 ${
          activo ? 'bg-primary/10 text-primary font-medium' : 'hover:bg-surface-50 hover:border-surface-200'
        } ${dragOver ? 'ring-2 ring-primary ring-inset bg-primary/5' : ''}`}
        onClick={() => onSeleccionar(nodo.id)}
        draggable={dndActivo}
        onDragStart={(e) => {
          e.stopPropagation();
          e.dataTransfer.setData(DND_MIME, serializarDnd({ kind: 'category', id: nodo.id }));
          e.dataTransfer.effectAllowed = 'move';
        }}
        onDragOver={(e) => {
          if (!dndActivo) return;
          e.preventDefault();
          e.dataTransfer.dropEffect = 'move';
          if (!dragOver) setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
      >
        {nodo.hijos.length > 0 ? (
          <button
            className="w-5 h-5 flex items-center justify-center shrink-0"
            onClick={(e) => { e.stopPropagation(); setExpandido(!expandido); }}
            aria-label={expandido ? 'Colapsar' : 'Expandir'}
          >
            <Icon name={expandido ? 'expand_more' : 'chevron_right'} className="text-[16px]" />
          </button>
        ) : (
          <span className="w-6 shrink-0" />
        )}
        <Icon name="folder" className={`text-[16px] shrink-0 ${activo ? 'text-primary' : 'text-on-surface-variant'}`} />
        <span className="flex-1 text-[13px] truncate">{nodo.nombre}</span>
        <span className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            className="p-0.5 rounded hover:bg-surface-200 text-on-surface-variant"
            title="Nueva subcategoría"
            onClick={(e) => { e.stopPropagation(); onCrear(nodo.id); }}
          >
            <Icon name="create_new_folder" className="text-[14px]" />
          </button>
          <button
            className="p-0.5 rounded hover:bg-surface-200 text-on-surface-variant"
            title="Renombrar"
            onClick={(e) => { e.stopPropagation(); onRenombrar(nodo); }}
          >
            <Icon name="edit" className="text-[14px]" />
          </button>
          <button
            className="p-0.5 rounded hover:bg-error/20 text-error"
            title="Borrar"
            onClick={(e) => { e.stopPropagation(); onBorrar(nodo); }}
          >
            <Icon name="delete" className="text-[14px]" />
          </button>
        </span>
      </div>
      {expandido && nodo.hijos.map((hijo) => (
        <NodoCategoria
          key={hijo.id}
          nodo={hijo}
          nivel={nivel + 1}
          seleccionada={seleccionada}
          dndActivo={dndActivo}
          onSeleccionar={onSeleccionar}
          onCrear={onCrear}
          onRenombrar={onRenombrar}
          onBorrar={onBorrar}
          onMoverCategoria={onMoverCategoria}
          onMoverPregunta={onMoverPregunta}
        />
      ))}
    </div>
  );
}

export function CategoriasTree({
  categorias,
  seleccionada,
  sinClasificarCount,
  onSeleccionar,
  onCrear,
  onRenombrar,
  onBorrar,
  onMoverCategoria,
  onMoverPregunta,
}: Props) {
  const arbol = buildTree(categorias);
  const dndActivo = Boolean(onMoverCategoria || onMoverPregunta);
  const [dragOverRaiz, setDragOverRaiz] = useState(false);
  const [dragOverSin, setDragOverSin] = useState(false);

  return (
    <div className="flex flex-col gap-1">
      {dndActivo && (
        <p className="text-label-sm text-on-surface-variant px-2 pb-1 flex items-center gap-1">
          <Icon name="drag_indicator" className="text-[14px]" />
          Arrastrá una categoría para anidarla, o soltá una pregunta sobre una categoría.
        </p>
      )}
      {/* Bucket "Sin clasificar" — solo si hay preguntas sin clasificar, mismo
          estilo que una categoría normal (no un color aparte). Acepta soltar
          preguntas para des-clasificarlas. */}
      {sinClasificarCount > 0 && (
        <div
          className={`flex items-center gap-2 px-2 py-2 rounded-lg cursor-pointer transition-all duration-150 ${
            seleccionada === null ? 'bg-primary/10 text-primary font-medium' : 'hover:bg-surface-50 hover:border-surface-200'
          } ${dragOverSin ? 'ring-2 ring-primary ring-inset bg-primary/5' : ''}`}
          onClick={() => onSeleccionar(null)}
          onDragOver={(e) => {
            if (!onMoverPregunta) return;
            e.preventDefault();
            if (!dragOverSin) setDragOverSin(true);
          }}
          onDragLeave={() => setDragOverSin(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOverSin(false);
            const payload = leerDnd(e);
            if (payload?.kind === 'question') onMoverPregunta?.(payload.id, null);
          }}
        >
          <span className="w-6 shrink-0" />
          <Icon
            name="folder_off"
            className={`text-[16px] shrink-0 ${seleccionada === null ? 'text-primary' : 'text-on-surface-variant'}`}
          />
          <span className="flex-1 text-[13px] truncate">Sin clasificar</span>
        </div>
      )}

      {arbol.map((nodo) => (
        <NodoCategoria
          key={nodo.id}
          nodo={nodo}
          nivel={0}
          seleccionada={seleccionada}
          dndActivo={dndActivo}
          onSeleccionar={onSeleccionar}
          onCrear={onCrear}
          onRenombrar={onRenombrar}
          onBorrar={onBorrar}
          onMoverCategoria={onMoverCategoria}
          onMoverPregunta={onMoverPregunta}
        />
      ))}

      {/* Zona para soltar y convertir una categoría en raíz (sacarla de su padre). */}
      {onMoverCategoria && (
        <div
          className={`mt-1 px-2 py-1.5 rounded-lg border border-dashed text-label-sm text-on-surface-variant transition-all ${
            dragOverRaiz ? 'border-primary bg-primary/5 text-primary' : 'border-surface-200'
          }`}
          onDragOver={(e) => { e.preventDefault(); if (!dragOverRaiz) setDragOverRaiz(true); }}
          onDragLeave={() => setDragOverRaiz(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOverRaiz(false);
            const payload = leerDnd(e);
            if (payload?.kind === 'category') onMoverCategoria(payload.id, null);
          }}
        >
          Soltá acá para dejar la categoría como raíz
        </div>
      )}

      <div className="mt-2 px-2">
        <Button
          variant="ghost"
          size="sm"
          icon="add"
          onClick={() => onCrear(null)}
          className="w-full justify-start text-on-surface-variant"
        >
          Nueva categoría raíz
        </Button>
      </div>
    </div>
  );
}
