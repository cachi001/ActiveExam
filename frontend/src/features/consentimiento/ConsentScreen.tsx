/**
 * Pantalla dedicada de consentimiento informado (C-08, feature consentimiento).
 *
 * - Lenguaje claro: muestra los cinco bloques (que/como/donde/cuanto/derechos)
 *   de la version vigente del texto, traidos del backend (RN-CO-01, US-003 CA-1).
 * - Accion afirmativa EXPLICITA: el boton "Acepto" arranca DESHABILITADO y solo
 *   se habilita cuando el estudiante marca conscientemente la casilla, que NO
 *   esta premarcada (RN-CO-02). No hay consentimiento por defecto.
 * - Via alternativa visible: "No consiento -> verificacion por proctor" nunca
 *   bloquea el examen (RN-CO-05, RN-GLB-02): escala a un proctor humano.
 *
 * La validez legal se garantiza ademas server-side (D2): el backend rechaza (422)
 * un acuse sin accion afirmativa; esta UI es la primera barrera, no la unica.
 *
 * Convencion del proyecto: componente en PascalCase (archivo y nombre).
 */

import { useEffect, useState } from "react";

interface ConsentText {
  version: string;
  bloques: Record<string, string>;
  hash_texto: string;
}

interface ConsentScreenProps {
  examId: string;
  authToken: string;
  apiBase?: string;
  onConsented?: (consentId: string) => void;
  onAlternativeChosen?: (mensajeId: string) => void;
}

const BLOQUE_LABELS: Record<string, string> = {
  que_se_recolecta: "Qué datos se recolectan",
  como_se_recolecta: "Cómo se recolectan",
  donde_se_almacena: "Dónde se almacenan",
  cuanto_tiempo: "Por cuánto tiempo",
  derechos_titular: "Tus derechos como titular",
};

export function ConsentScreen({
  examId,
  authToken,
  apiBase = "/api/v1",
  onConsented,
  onAlternativeChosen,
}: ConsentScreenProps) {
  const [text, setText] = useState<ConsentText | null>(null);
  // Estado INICIAL false: la accion afirmativa nunca viene premarcada (RN-CO-02).
  const [affirmative, setAffirmative] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${authToken}`,
  };

  useEffect(() => {
    fetch(`${apiBase}/consent/text`, { headers })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("No se pudo cargar el texto"))))
      .then(setText)
      .catch((e) => setError(String(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiBase, authToken]);

  async function handleConsent() {
    if (!affirmative || !text) return; // doble barrera en UI
    setSubmitting(true);
    setError(null);
    try {
      const resp = await fetch(`${apiBase}/consent`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          exam_id: examId,
          version_texto: text.version,
          affirmative_action: true,
        }),
      });
      if (!resp.ok) {
        // 422 si el backend rechaza por falta de accion afirmativa (D2).
        throw new Error(`Consentimiento rechazado (${resp.status})`);
      }
      const data = await resp.json();
      onConsented?.(data.id);
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleAlternative() {
    setSubmitting(true);
    setError(null);
    try {
      // No consentir NUNCA aborta el examen: escala a proctor (RN-GLB-02).
      const resp = await fetch(`${apiBase}/consent/alternative`, {
        method: "POST",
        headers,
        body: JSON.stringify({ exam_id: examId }),
      });
      if (!resp.ok) throw new Error(`No se pudo escalar la vía alternativa (${resp.status})`);
      const data = await resp.json();
      onAlternativeChosen?.(data.mensaje_id);
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  }

  if (error && !text) return <div role="alert">Error: {error}</div>;
  if (!text) return <div>Cargando consentimiento…</div>;

  return (
    <section aria-labelledby="consent-title" className="consent-screen">
      <h1 id="consent-title">Consentimiento informado</h1>
      <p className="consent-version">Versión del texto: {text.version}</p>

      <dl className="consent-blocks">
        {Object.entries(text.bloques).map(([clave, valor]) => (
          <div key={clave}>
            <dt>{BLOQUE_LABELS[clave] ?? clave}</dt>
            <dd>{valor}</dd>
          </div>
        ))}
      </dl>

      {/* Accion afirmativa: casilla NO premarcada (RN-CO-02). */}
      <label className="consent-affirmative">
        <input
          type="checkbox"
          checked={affirmative}
          onChange={(e) => setAffirmative(e.target.checked)}
        />
        Leí y entiendo la información, y consiento de forma libre y expresa el
        tratamiento de mis datos biométricos para este examen.
      </label>

      {error && <div role="alert">Error: {error}</div>}

      <div className="consent-actions">
        <button
          type="button"
          disabled={!affirmative || submitting}
          onClick={handleConsent}
        >
          Acepto y consiento
        </button>

        <button type="button" disabled={submitting} onClick={handleAlternative}>
          No consiento — verificación alternativa por proctor
        </button>
      </div>
    </section>
  );
}

export default ConsentScreen;
