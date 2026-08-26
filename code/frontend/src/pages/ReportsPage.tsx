import { useState, type FormEvent } from "react";

import { ApiError, downloadReportPdf, generateReport } from "../api/client";
import type { ReportFilter, ReportResponse } from "../api/types";
import { useAuth } from "../auth/AuthContext";

export function ReportsPage() {
  const { auth } = useAuth();
  const [filters, setFilters] = useState<ReportFilter>({});
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!auth) return;
    setLoading(true);
    setError(null);
    setReport(null);
    try {
      setReport(await generateReport(filters, auth.token));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  async function handleDownloadPdf() {
    if (!auth || !report) return;
    const blob = await downloadReportPdf(report.report_id, auth.token);
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${report.report_id}.pdf`;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <section>
      <h2>Compliance Report (FR-4)</h2>
      <p className="muted">Compliance Head only. Aggregates already-screened transactions for the given filter.</p>
      <form onSubmit={handleSubmit} className="stacked-form">
        <label>
          Transaction type
          <select
            value={filters.transaction_type ?? ""}
            onChange={(e) => setFilters({ ...filters, transaction_type: e.target.value || undefined })}
          >
            <option value="">Any</option>
            <option value="cross_border_payment">Cross-border payment</option>
            <option value="derivative_trade">Derivative trade</option>
            <option value="investment">Investment</option>
            <option value="lending">Lending</option>
          </select>
        </label>
        <label>
          Jurisdiction
          <select
            value={filters.jurisdiction ?? ""}
            onChange={(e) => setFilters({ ...filters, jurisdiction: e.target.value || undefined })}
          >
            <option value="">Any</option>
            <option value="IN">India</option>
            <option value="EU">EU</option>
            <option value="US">US</option>
          </select>
        </label>
        <button type="submit" disabled={loading}>
          {loading ? "Generating…" : "Generate report"}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {report && (
        <div className="result-card">
          <div className="result-header">
            <span className="status-chip">{report.transaction_count} transaction(s)</span>
            <button type="button" onClick={handleDownloadPdf}>
              Download PDF
            </button>
          </div>
          <pre className="markdown-preview">{report.markdown}</pre>
        </div>
      )}
    </section>
  );
}
