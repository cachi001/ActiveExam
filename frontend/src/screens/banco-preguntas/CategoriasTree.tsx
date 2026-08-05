import { useState } from 'react';
import { Icon, Button } from '../../ui/components';
import type { CategoriaPregunta } from '../../lib/apiAdmin/bancoPreguntasApi';

interface NodoArbol extends CategoriaPregunta {
  hijos: NodoArbol[];
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
  onSeleccionar: (id: string | null) => void;
  onCrear: (padreId: string | null) => void;
  onRenombrar: (cat: CategoriaPregunta) => void;
  onBorrar: (cat: CategoriaPregunta) => void;
}

function NodoCategoria({
  nodo,
  nivel,
  seleccionada,
  onSeleccionar,
  onCrear,
  onRenombrar,
  onBorrar,
}: {
  nodo: NodoArbol;
  nivel: number;
  seleccionada: string | null;
  onSeleccionar: (id: string | null) => void;
  onCrear: (padreId: string | null) => void;
  onRenombrar: (cat: CategoriaPregunta) => void;
  onBorrar: (cat: CategoriaPregunta) => void;
}) {
  const [expandido, setExpandido] = useState(false);
  const activo = seleccionada === nodo.id;

  return (
    <div style={{ paddingLeft: nivel * 16 }}>
      <div
        className={`flex items-center gap-1 px-2 py-2 rounded-lg cursor-pointer group transition-all duration-150 ${
          activo ? 'bg-primary/10 text-primary font-semibold' : 'hover:bg-surface-50 hover:border-surface-200'
        }`}
        onClick={() => onSeleccionar(nodo.id)}
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
        <span className="flex-1 text-body-sm truncate">{nodo.nombre}</span>
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
          onSeleccionar={onSeleccionar}
          onCrear={onCrear}
          onRenombrar={onRenombrar}
          onBorrar={onBorrar}
        />
      ))}
    </div>
  );
}

export function CategoriasTree({
  categorias,
  seleccionada,
  onSeleccionar,
  onCrear,
  onRenombrar,
  onBorrar,
}: Props) {
  const arbol = buildTree(categorias);

  return (
    <div className="flex flex-col gap-1">
      {/* Bucket "Sin clasificar" — siempre visible al tope */}
      <div
        className={`flex items-center gap-1 px-2 py-2 rounded-lg cursor-pointer transition-all duration-150 ${
          seleccionada === null
            ? 'bg-primary/10 text-primary font-semibold'
            : 'text-surface-500 hover:bg-surface-50 hover:text-surface-700'
        }`}
        onClick={() => onSeleccionar(null)}
      >
        <span className="w-6 shrink-0" />
        <Icon
          name="inbox"
          className={`text-[16px] shrink-0 ${seleccionada === null ? 'text-primary' : 'text-on-surface-variant'}`}
        />
        <span className="flex-1 text-body-sm">Sin clasificar</span>
      </div>

      {arbol.map((nodo) => (
        <NodoCategoria
          key={nodo.id}
          nodo={nodo}
          nivel={0}
          seleccionada={seleccionada}
          onSeleccionar={onSeleccionar}
          onCrear={onCrear}
          onRenombrar={onRenombrar}
          onBorrar={onBorrar}
        />
      ))}

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
