import { useState, type FormEvent } from "react";

import { askQuestion, ApiError } from "../api/client";
import type { QaResponse } from "../api/types";
import { useAuth } from "../auth/AuthContext";

export function QAPage() {
  const { auth } = useAuth();
  const [query, setQuery] = useState("What are the Tier 1 capital requirements under Basel III?");
  const [jurisdiction, setJurisdiction] = useState("");
  const [response, setResponse] = useState<QaResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!auth) return;
    setLoading(true);
    setError(null);
    setResponse(null);
    try {
      const result = await askQuestion(
        { query, jurisdictions: jurisdiction ? [jurisdiction] : undefined },
        auth.token,
      );
      setResponse(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section>
      <h2>Regulatory Q&amp;A (FR-1)</h2>
      <form onSubmit={handleSubmit} className="stacked-form">
        <label>
          Question
          <textarea value={query} onChange={(e) => setQuery(e.target.value)} rows={3} maxLength={2000} required />
        </label>
        <label>
          Jurisdiction (optional)
          <select value={jurisdiction} onChange={(e) => setJurisdiction(e.target.value)}>
            <option value="">Any</option>
            <option value="IN">India</option>
            <option value="EU">EU</option>
            <option value="US">US</option>
          </select>
        </label>
        <button type="submit" disabled={loading}>
          {loading ? "Asking…" : "Ask"}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {response && (
        <div className="result-card">
          <p className="status-chip">{response.status}</p>
          <p>{response.answer}</p>
          {response.citations.length > 0 && (
            <>
              <h4>Citations</h4>
              <ul className="citation-list">
                {response.citations.map((citation) => (
                  <li key={citation}>{citation}</li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </section>
  );
}
