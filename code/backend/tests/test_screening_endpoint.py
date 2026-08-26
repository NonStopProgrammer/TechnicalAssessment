SCENARIO_1_PAYLOAD = {
    "amount": 2000000,
    "currency": "USD",
    "counterparty": "Meridian Offshore Holdings Ltd",
    "counterparty_kyc_status": "not_verified",
    "jurisdictions": ["IN"],
    "instrument_type": "wire_transfer",
    "customer_type": "institutional",
    "transaction_type": "cross_border_payment",
    "counterparty_jurisdiction_risk": "high",
}


def test_screening_rejects_wrong_role(client, auditor_headers):
    response = client.post("/api/v1/screening", json=SCENARIO_1_PAYLOAD, headers=auditor_headers)
    assert response.status_code == 403


def test_screening_scenario_1_is_critical_or_high_with_citations(client, officer_headers):
    response = client.post("/api/v1/screening", json=SCENARIO_1_PAYLOAD, headers=officer_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["risk_rating"] in ("HIGH", "CRITICAL")
    assert body["citations"]
    assert body["provenance"]["prompt_template_id"] == "transaction_screening"


def test_screening_rejects_missing_required_field_by_name(client, officer_headers):
    incomplete_payload = {"currency": "USD"}
    response = client.post("/api/v1/screening", json=incomplete_payload, headers=officer_headers)

    assert response.status_code == 400
    body = response.json()
    fields = {e["field"] for e in body["errors"]}
    assert "amount" in fields
