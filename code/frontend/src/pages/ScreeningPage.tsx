import { useState, type FormEvent } from "react";

import { ApiError, screenTransaction } from "../api/client";
import { CitationList } from "../components/CitationList";
import { RiskBadge } from "../components/RiskBadge";
import type { ComplianceAssessment, TransactionPayload } from "../api/types";
import { useAuth } from "../auth/AuthContext";

const DEFAULT_PAYLOAD: TransactionPayload = {
  amount: 2000000,
  currency: "USD",
  counterparty: "Meridian Offshore Holdings Ltd",
  counterparty_kyc_status: "not_verified",
  jurisdictions: ["IN"],
  instrument_type: "wire_transfer",
  customer_type: "institutional",
  transaction_type: "cross_border_payment",
  counterparty_jurisdiction_risk: "high",
};

// Mirrors agentic/seed_data/transactions.json — the assignment's 4
// reference scenarios, for one-click demoing without needing a separate
// "fetch seeded transaction" REST endpoint.
const QUICK_SCENARIOS: Record<string, TransactionPayload> = {
  "TXN-1001 — cross-border payment": DEFAULT_PAYLOAD,
  "TXN-1002 — intra-group derivative": {
    amount: 75000000,
    currency: "USD",
    counterparty: "FinServ Capital Markets (Singapore) Pte Ltd",
    counterparty_kyc_status: "verified",
    jurisdictions: ["IN", "EU"],
    instrument_type: "interest_rate_swap",
    customer_type: "intra_group",
    transaction_type: "derivative_trade",
  },
  "TXN-1003 — retail structured note": {
    amount: 150000,
    currency: "EUR",
    counterparty: "Individual Retail Client - J. Dupont",
    counterparty_kyc_status: "verified",
    jurisdictions: ["EU"],
    instrument_type: "structured_note",
    customer_type: "retail",
    transaction_type: "investment",
    is_appropriateness_assessed: false,
  },
  "TXN-1004 — NBFC priority-sector lending": {
    amount: 4200000,
    currency: "INR",
    counterparty: "Sunrise Agri Finance NBFC Ltd",
    counterparty_kyc_status: "verified",
    jurisdictions: ["IN"],
    instrument_type: "term_loan",
    customer_type: "institutional",
    transaction_type: "lending",
    is_priority_sector: true,
  },
};

export function ScreeningPage() {
  const { auth } = useAuth();
  const [payloadJson, setPayloadJson] = useState(JSON.stringify(DEFAULT_PAYLOAD, null, 2));
  const [assessment, setAssessment] = useState<ComplianceAssessment | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!auth) return;
    setLoading(true);
    setError(null);
    setAssessment(null);
    try {
      const payload = JSON.parse(payloadJson) as TransactionPayload;
      const result = await screenTransaction(payload, auth.token);
      setAssessment(result);
    } catch (err) {
      if (err instanceof SyntaxError) setError("Payload is not valid JSON.");
      else if (err instanceof ApiError) setError(err.message);
      else setError("Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section>
      <h2>Transaction Screening (FR-2)</h2>
      <div className="quick-scenarios">
        {Object.entries(QUICK_SCENARIOS).map(([label, payload]) => (
          <button key={label} type="button" onClick={() => setPayloadJson(JSON.stringify(payload, null, 2))}>
            {label}
          </button>
        ))}
      </div>
      <form onSubmit={handleSubmit} className="stacked-form">
        <label>
          Transaction payload (JSON)
          <textarea value={payloadJson} onChange={(e) => setPayloadJson(e.target.value)} rows={14} spellCheck={false} />
        </label>
        <button type="submit" disabled={loading}>
          {loading ? "Screening…" : "Screen transaction"}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {assessment && (
        <div className="result-card">
          <div className="result-header">
            <RiskBadge rating={assessment.risk_rating} />
            <span className="status-chip">{assessment.status}</span>
            <span className="muted">confidence {assessment.confidence_score.toFixed(2)}</span>
          </div>

          <p>{assessment.narrative}</p>

          <h4>Applicable frameworks</h4>
          <p>{assessment.applicable_frameworks.join(", ") || "—"}</p>

          <h4>Rule triggers</h4>
          <ul>
            {assessment.rule_triggers.map((trigger) => (
              <li key={trigger.rule_id}>
                <strong>{trigger.severity}</strong> — {trigger.description}
              </li>
            ))}
          </ul>

          <h4>Required actions</h4>
          <ul>
            {assessment.required_actions.map((action, index) => (
              <li key={index}>
                {action.action} — <span className="muted">{action.reason}</span>
              </li>
            ))}
          </ul>

          {assessment.assumptions.length > 0 && (
            <>
              <h4>Assumptions (missing facts)</h4>
              <ul>
                {assessment.assumptions.map((assumption, index) => (
                  <li key={index}>{assumption}</li>
                ))}
              </ul>
            </>
          )}

          {assessment.conflicts.length > 0 && (
            <>
              <h4>Cross-framework conflicts</h4>
              <ul>
                {assessment.conflicts.map((conflict, index) => (
                  <li key={index}>{conflict.description}</li>
                ))}
              </ul>
            </>
          )}

          <h4>Citations</h4>
          <CitationList citations={assessment.citations} />
        </div>
      )}
    </section>
  );
}
