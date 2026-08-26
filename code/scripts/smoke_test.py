"""End-to-end smoke test against a *running* backend (docker-compose up, or
`uvicorn backend.main:api`). Exercises FR-1, FR-2, FR-4, and SEC-2.3 over
real HTTP, printing each response — this is the "sample outputs" the
assignment's submission checklist asks for, runnable on demand rather than
only captured once in a README.

    python -m scripts.smoke_test [--base-url http://localhost:8080/api/v1]
"""

import argparse
import json
import sys

import httpx

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


def _print_step(title: str) -> None:
    print(f"\n=== {title} ===")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8080/api/v1")
    args = parser.parse_args()

    with httpx.Client(base_url=args.base_url, timeout=30.0) as client:
        _print_step("Health check")
        health = client.get("/health")
        health.raise_for_status()
        print(json.dumps(health.json(), indent=2))

        _print_step("Issue dev tokens")
        officer_token = client.post(
            "/auth/dev-token", json={"user_id": "officer@finserv.demo", "role": "compliance_officer"}
        ).json()["access_token"]
        head_token = client.post(
            "/auth/dev-token", json={"user_id": "head@finserv.demo", "role": "compliance_head"}
        ).json()["access_token"]
        auditor_token = client.post(
            "/auth/dev-token", json={"user_id": "auditor@finserv.demo", "role": "internal_auditor"}
        ).json()["access_token"]
        print("Tokens issued for officer, head, auditor.")

        officer_headers = {"Authorization": f"Bearer {officer_token}"}
        head_headers = {"Authorization": f"Bearer {head_token}"}
        auditor_headers = {"Authorization": f"Bearer {auditor_token}"}

        _print_step("FR-1: Q&A")
        qa = client.post(
            "/qa",
            json={"query": "What are the Tier 1 capital requirements under Basel III?", "jurisdictions": ["IN"]},
            headers=officer_headers,
        )
        qa.raise_for_status()
        print(json.dumps(qa.json(), indent=2))

        _print_step("FR-2: Transaction screening (reference scenario 1)")
        screening = client.post("/screening", json=SCENARIO_1_PAYLOAD, headers=officer_headers)
        screening.raise_for_status()
        assessment = screening.json()
        print(f"risk_rating={assessment['risk_rating']} status={assessment['status']}")
        print(json.dumps(assessment, indent=2)[:1500] + " ...")

        _print_step("FR-4: Report generation")
        report = client.post("/reports", json={}, headers=head_headers)
        report.raise_for_status()
        report_body = report.json()
        print(f"report_id={report_body['report_id']} transaction_count={report_body['transaction_count']}")

        _print_step("SEC-2.3: Audit trail (internal_auditor)")
        audit = client.get("/audit-log", headers=auditor_headers)
        audit.raise_for_status()
        print(f"{len(audit.json())} audit log entries visible to the auditor.")

    print("\nSmoke test completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
