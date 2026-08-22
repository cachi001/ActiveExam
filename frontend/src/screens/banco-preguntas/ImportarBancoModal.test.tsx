/**
 * Test de componente del selector "Importar dentro de la carpeta" (bug real,
 * 2026-08-21, campus FRM): Moodle nunca exporta una categoría propia para el
 * nodo "top" — las subcategorías quedaban sueltas en ActiveExam sin ningún
 * padre común. El docente ahora elige una categoría YA EXISTENTE (selector,
 * no texto tipeado) como destino de todo el import.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { ImportarBancoModal } from './ImportarBancoModal';
import type {
  CategoriaPregunta,
  ImportarBancoXmlResult,
  PreviewImportBancoResult,
} from '../../lib/apiAdmin/bancoPreguntasApi';

const { listarCategorias, previewImportarBancoXml, importarBancoXml } = vi.hoisted(() => ({
  listarCategorias: vi.fn(),
  previewImportarBancoXml: vi.fn(),
  importarBancoXml: vi.fn(),
}));

vi.mock('../../lib/apiAdmin/bancoPreguntasApi', () => ({
  listarCategorias,
  previewImportarBancoXml,
  importarBancoXml,
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const PREVIEW_BASICO: PreviewImportBancoResult = {
  categorias: [{ ruta: ['Clase 1'], preguntas_por_tipo: { multichoice: 2 }, preguntas: [] }],
  sin_categoria_por_tipo: {},
  omitidas: [],
  total_preguntas: 2,
  sin_categoria_preguntas: [],
};

const RESUMEN_BASICO: ImportarBancoXmlResult = {
  preguntas_nuevas: 2,
  preguntas_actualizadas: 0,
  omitidas: [],
  nuevas: [],
  actualizadas: [],
};

const CATEGORIAS_EXISTENTES: CategoriaPregunta[] = [
  {
    id: 'root-1',
    nombre: 'Programación 3-2026 Agosto',
    materia_id: 'm1',
    categoria_padre_id: null,
    creada_en: '2026-01-01T00:00:00',
  },
  {
    id: 'sub-1',
    nombre: 'Clase vieja',
    materia_id: 'm1',
    categoria_padre_id: 'root-1',
    creada_en: '2026-01-01T00:00:00',
  },
];

function subirArchivo() {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  const archivo = new File(['<quiz></quiz>'], 'export.xml', { type: 'text/xml' });
  fireEvent.change(input, { target: { files: [archivo] } });
}

describe('ImportarBancoModal — selector de categoría destino', () => {
  it('muestra el selector con las categorías existentes cuando hay al menos una', async () => {
    listarCategorias.mockResolvedValue(CATEGORIAS_EXISTENTES);
    previewImportarBancoXml.mockResolvedValue(PREVIEW_BASICO);

    render(<ImportarBancoModal abierto materiaId="m1" onCerrar={() => {}} onImportado={() => {}} />);

    subirArchivo();

    await waitFor(() => expect(screen.queryByText('Importar dentro de la carpeta')).not.toBeNull());
    expect(screen.queryByText('— Sin carpeta (como hoy) —')).not.toBeNull();
    expect(screen.queryByText(/Programación 3-2026 Agosto/)).not.toBeNull();
    expect(screen.queryByText(/Clase vieja/)).not.toBeNull();
  });

  it('no muestra el selector si la materia todavía no tiene ninguna categoría', async () => {
    listarCategorias.mockResolvedValue([]);
    previewImportarBancoXml.mockResolvedValue(PREVIEW_BASICO);

    render(<ImportarBancoModal abierto materiaId="m1" onCerrar={() => {}} onImportado={() => {}} />);

    subirArchivo();

    await waitFor(() => expect(screen.queryByText(/para importar/)).not.toBeNull());
    expect(screen.queryByText('Importar dentro de la carpeta')).toBeNull();
  });

  it('al confirmar, envía la categoría elegida como categoriaPadreId', async () => {
    listarCategorias.mockResolvedValue(CATEGORIAS_EXISTENTES);
    previewImportarBancoXml.mockResolvedValue(PREVIEW_BASICO);
    importarBancoXml.mockResolvedValue(RESUMEN_BASICO);

    render(<ImportarBancoModal abierto materiaId="m1" onCerrar={() => {}} onImportado={() => {}} />);

    subirArchivo();
    await waitFor(() => expect(screen.queryByText('Importar dentro de la carpeta')).not.toBeNull());

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'sub-1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar importación' }));

    await waitFor(() => expect(importarBancoXml).toHaveBeenCalledTimes(1));
    expect(importarBancoXml).toHaveBeenCalledWith('m1', expect.any(File), [], 'sub-1');
  });

  it('sin elegir carpeta, envía null (comportamiento actual sin cambios)', async () => {
    listarCategorias.mockResolvedValue(CATEGORIAS_EXISTENTES);
    previewImportarBancoXml.mockResolvedValue(PREVIEW_BASICO);
    importarBancoXml.mockResolvedValue(RESUMEN_BASICO);

    render(<ImportarBancoModal abierto materiaId="m1" onCerrar={() => {}} onImportado={() => {}} />);

    subirArchivo();
    await waitFor(() => expect(screen.queryByText('Importar dentro de la carpeta')).not.toBeNull());

    fireEvent.click(screen.getByRole('button', { name: 'Confirmar importación' }));

    await waitFor(() => expect(importarBancoXml).toHaveBeenCalledTimes(1));
    expect(importarBancoXml).toHaveBeenCalledWith('m1', expect.any(File), [], null);
  });
});
