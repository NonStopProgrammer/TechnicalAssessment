import { useEffect, useState } from "react";

import { ApiError, getAuditLog } from "../api/client";
import type { AuditLogEntry } from "../api/types";
import { useAuth } from "../auth/AuthContext";

export function AuditTrailPage() {
  const { auth } = useAuth();
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!auth) return;
    setLoading(true);
    getAuditLog(auth.token)
      .then(setEntries)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load the audit trail."))
      .finally(() => setLoading(false));
  }, [auth]);

  return (
    <section>
      <h2>Audit Trail (SEC-2.3)</h2>
      <p className="muted">Internal Auditor only — read-only, no query/screen access needed.</p>

      {loading && <p>Loading…</p>}
      {error && <p className="error">{error}</p>}

      {!loading && !error && (
        <table className="audit-table">
          <thead>
            <tr>
              <th>Request</th>
              <th>Endpoint</th>
              <th>User</th>
              <th>Model</th>
              <th>Confidence</th>
              <th>When</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => (
              <tr key={entry.id}>
                <td>
                  <code>{entry.request_id}</code>
                </td>
                <td>{entry.endpoint}</td>
                <td>
                  {entry.user_id} ({entry.role})
                </td>
                <td>{entry.model_id ?? "—"}</td>
                <td>{entry.confidence_score?.toFixed(2) ?? "—"}</td>
                <td>{new Date(entry.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
