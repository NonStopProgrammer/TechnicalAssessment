SCENARIO_PAYLOAD = {
    "amount": 4200000,
    "currency": "INR",
    "counterparty": "Sunrise Agri Finance NBFC Ltd",
    "counterparty_kyc_status": "verified",
    "jurisdictions": ["IN"],
    "instrument_type": "term_loan",
    "customer_type": "institutional",
    "transaction_type": "lending",
    "is_priority_sector": True,
}


def test_report_generation_rejects_wrong_role(client, officer_headers):
    response = client.post("/api/v1/reports", json={}, headers=officer_headers)
    assert response.status_code == 403


def test_generate_and_download_report(client, officer_headers, head_headers):
    screening_response = client.post("/api/v1/screening", json=SCENARIO_PAYLOAD, headers=officer_headers)
    assert screening_response.status_code == 200

    report_response = client.post("/api/v1/reports", json={}, headers=head_headers)
    assert report_response.status_code == 200
    body = report_response.json()
    assert body["summary_stats"]["total_transactions"] >= 1
    report_id = body["report_id"]

    markdown_response = client.get(f"/api/v1/reports/{report_id}/markdown", headers=head_headers)
    assert markdown_response.status_code == 200
    assert "Executive Summary" in markdown_response.text

    pdf_response = client.get(f"/api/v1/reports/{report_id}/pdf", headers=head_headers)
    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"] == "application/pdf"


def test_download_unknown_report_is_404(client, head_headers):
    response = client.get("/api/v1/reports/rpt_does_not_exist/markdown", headers=head_headers)
    assert response.status_code == 404


def test_audit_log_readable_by_auditor_only(client, auditor_headers, officer_headers):
    forbidden = client.get("/api/v1/audit-log", headers=officer_headers)
    assert forbidden.status_code == 403

    allowed = client.get("/api/v1/audit-log", headers=auditor_headers)
    assert allowed.status_code == 200
    assert isinstance(allowed.json(), list)
