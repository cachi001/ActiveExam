import { useState } from 'react';
import { altaInlineMateriaComision } from '../../lib/examContentAdmin';

interface OmitidaItem {
  tipo: string;
  nombre: string;
  motivo: string;
}

interface ImportReport {
  examen_id: string;
  importadas: number;
  omitidas: OmitidaItem[];
}

export default function MoodleImportPage() {
  const [file, setFile] = useState<File | null>(null);
  const [titulo, setTitulo] = useState('');
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<ImportReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Asociación OPCIONAL a comisión (D11): su ausencia NO bloquea importar ni rendir.
  const [materiaCodigo, setMateriaCodigo] = useState('');
  const [materiaNombre, setMateriaNombre] = useState('');
  const [comisionCodigo, setComisionCodigo] = useState('');
  const [comisionNombre, setComisionNombre] = useState('');
  const [asocLoading, setAsocLoading] = useState(false);
  const [asocError, setAsocError] = useState<string | null>(null);
  const [asocOk, setAsocOk] = useState(false);

  async function handleAsociar(e: React.FormEvent) {
    e.preventDefault();
    if (!report) return;
    setAsocLoading(true);
    setAsocError(null);
    setAsocOk(false);
    try {
      await altaInlineMateriaComision(
        { codigo: materiaCodigo.trim(), nombre: materiaNombre.trim() },
        { codigo: comisionCodigo.trim(), nombre: comisionNombre.trim() },
        report.examen_id,
      );
      setAsocOk(true);
    } catch (err) {
      setAsocError(err instanceof Error ? err.message : 'Error al asociar la comisión.');
    } finally {
      setAsocLoading(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;

    setLoading(true);
    setError(null);
    setReport(null);
    setAsocOk(false);
    setAsocError(null);

    const formData = new FormData();
    formData.append('file', file);
    if (titulo.trim()) formData.append('titulo', titulo.trim());

    try {
      const resp = await fetch('/api/v1/exam-content/moodle-import', {
        method: 'POST',
        body: formData,
      });
      if (resp.ok) {
        setReport(await resp.json());
      } else {
        const body = await resp.json().catch(() => ({}));
        setError(body?.detail?.mensaje ?? body?.detail ?? `Error ${resp.status}`);
      }
    } catch {
      setError('Error de red al importar el examen.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-lg mx-auto p-lg space-y-lg">
      <h1 className="text-headline-sm font-semibold text-on-surface">
        Importar examen desde Moodle XML
      </h1>

      <form onSubmit={handleSubmit} className="space-y-md">
        <div className="space-y-xs">
          <label className="text-label-md text-on-surface-variant" htmlFor="moodle-file">
            Archivo XML de Moodle
          </label>
          <input
            id="moodle-file"
            type="file"
            accept=".xml"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="block w-full text-label-md text-on-surface
              file:mr-sm file:py-xs file:px-md
              file:rounded-lg file:border-0
              file:bg-primary file:text-on-primary
              hover:file:bg-primary-700 cursor-pointer"
          />
        </div>

        <div className="space-y-xs">
          <label className="text-label-md text-on-surface-variant" htmlFor="moodle-titulo">
            Título del examen <span className="text-on-surface-variant/60">(opcional)</span>
          </label>
          <input
            id="moodle-titulo"
            type="text"
            value={titulo}
            onChange={(e) => setTitulo(e.target.value)}
            placeholder="Ej: Parcial Álgebra 2025-1"
            className="w-full border border-outline-variant rounded-xl px-sm py-base
              text-label-md bg-surface outline-none focus:border-primary transition-colors"
          />
        </div>

        <button
          type="submit"
          disabled={!file || loading}
          className="w-full py-sm px-md rounded-xl bg-primary text-on-primary
            text-label-md font-semibold shadow-sm
            hover:bg-primary-700 active:bg-primary-800
            disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? 'Importando…' : 'Importar'}
        </button>
      </form>

      {error && (
        <div className="rounded-xl bg-error-50 border border-error-200 p-md text-label-md text-error-700">
          {error}
        </div>
      )}

      {report && (
        <div className="rounded-xl bg-surface-container p-md space-y-sm">
          <p className="text-label-md font-semibold text-on-surface">
            Importadas: {report.importadas} preguntas
          </p>
          <p className="text-label-sm text-on-surface-variant">
            ID del examen: {report.examen_id}
          </p>
          {report.omitidas.length > 0 && (
            <div className="space-y-xs">
              <p className="text-label-sm font-semibold text-on-surface-variant">
                Omitidas ({report.omitidas.length}):
              </p>
              <ul className="space-y-xs">
                {report.omitidas.map((o, i) => (
                  <li key={i} className="text-label-sm text-on-surface-variant">
                    <span className="font-mono bg-surface-container-high px-xs rounded">
                      {o.tipo}
                    </span>{' '}
                    {o.nombre} — {o.motivo}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {report && (
        <form
          onSubmit={handleAsociar}
          className="rounded-xl bg-surface-container p-md space-y-sm"
          aria-label="Asociar comisión"
        >
          <p className="text-label-md font-semibold text-on-surface">
            Asociar a una comisión{' '}
            <span className="text-on-surface-variant/60">(opcional)</span>
          </p>
          <p className="text-label-sm text-on-surface-variant">
            El examen ya quedó importado y rendible. Podés asociarlo a una materia y
            comisión ahora o más tarde; no es obligatorio.
          </p>

          <div className="grid grid-cols-2 gap-sm">
            <input
              aria-label="Código de materia"
              placeholder="Código materia"
              value={materiaCodigo}
              onChange={(e) => setMateriaCodigo(e.target.value)}
              className="border border-outline-variant rounded-xl px-sm py-base text-label-md bg-surface outline-none focus:border-primary"
            />
            <input
              aria-label="Nombre de materia"
              placeholder="Nombre materia"
              value={materiaNombre}
              onChange={(e) => setMateriaNombre(e.target.value)}
              className="border border-outline-variant rounded-xl px-sm py-base text-label-md bg-surface outline-none focus:border-primary"
            />
            <input
              aria-label="Código de comisión"
              placeholder="Código comisión"
              value={comisionCodigo}
              onChange={(e) => setComisionCodigo(e.target.value)}
              className="border border-outline-variant rounded-xl px-sm py-base text-label-md bg-surface outline-none focus:border-primary"
            />
            <input
              aria-label="Nombre de comisión"
              placeholder="Nombre comisión"
              value={comisionNombre}
              onChange={(e) => setComisionNombre(e.target.value)}
              className="border border-outline-variant rounded-xl px-sm py-base text-label-md bg-surface outline-none focus:border-primary"
            />
          </div>

          <button
            type="submit"
            disabled={
              asocLoading ||
              !materiaCodigo.trim() ||
              !materiaNombre.trim() ||
              !comisionCodigo.trim() ||
              !comisionNombre.trim()
            }
            className="w-full py-sm px-md rounded-xl bg-primary text-on-primary text-label-md font-semibold shadow-sm hover:bg-primary-700 active:bg-primary-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {asocLoading ? 'Asociando…' : 'Asociar comisión'}
          </button>

          {asocError && (
            <div className="rounded-xl bg-error-50 border border-error-200 p-md text-label-sm text-error-700">
              {asocError}
            </div>
          )}
          {asocOk && (
            <div className="rounded-xl bg-surface-container-high p-md text-label-sm text-on-surface">
              Comisión asociada al examen.
            </div>
          )}
        </form>
      )}
    </div>
  );
}
