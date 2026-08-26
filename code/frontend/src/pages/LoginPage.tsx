import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import type { UserRole } from "../api/types";
import { useAuth } from "../auth/AuthContext";

const ROLES: { value: UserRole; label: string }[] = [
  { value: "compliance_officer", label: "Compliance Officer (Q&A + Screening)" },
  { value: "compliance_head", label: "Compliance Head (+ Reports)" },
  { value: "internal_auditor", label: "Internal Auditor (Audit Trail, read-only)" },
  { value: "platform_admin", label: "Platform Admin" },
];

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [userId, setUserId] = useState("officer@finserv.demo");
  const [role, setRole] = useState<UserRole>("compliance_officer");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(userId, role);
      navigate("/qa");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not sign in — is the backend running?");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="centered-card">
      <h1>FinServ Compliance Assistant</h1>
      <p className="muted">
        DEV-ONLY sign-in — mints a demo JWT for the chosen role (see <code>backend/core/security.py</code>).
        A real deployment authenticates against Keycloak instead.
      </p>
      <form onSubmit={handleSubmit}>
        <label>
          User ID
          <input value={userId} onChange={(e) => setUserId(e.target.value)} required />
        </label>
        <label>
          Role
          <select value={role} onChange={(e) => setRole(e.target.value as UserRole)}>
            {ROLES.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
        </label>
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={submitting}>
          {submitting ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
