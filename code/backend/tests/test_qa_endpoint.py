def test_health_check(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_qa_requires_auth(client):
    response = client.post("/api/v1/qa", json={"query": "What is Basel III?"})
    assert response.status_code in (401, 403)


def test_qa_returns_cited_or_insufficient_answer(client, officer_headers):
    response = client.post(
        "/api/v1/qa",
        json={"query": "What CET1 ratio must banks maintain under Basel III?", "jurisdictions": ["IN"]},
        headers=officer_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] in ("answered", "insufficient_context")


def test_qa_rejects_empty_query_with_named_field(client, officer_headers):
    response = client.post("/api/v1/qa", json={"query": ""}, headers=officer_headers)
    assert response.status_code == 400
    body = response.json()
    assert body["detail"] == "validation_error"
    assert body["errors"][0]["field"] == "query"


def test_qa_declines_off_topic_question(client, officer_headers):
    response = client.post("/api/v1/qa", json={"query": "What's a good recipe for pasta?"}, headers=officer_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "off_topic"


def test_qa_rejects_wrong_role(client, auditor_headers):
    response = client.post("/api/v1/qa", json={"query": "What is Basel III?"}, headers=auditor_headers)
    assert response.status_code == 403
