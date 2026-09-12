import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def create_incident(client: TestClient, title: str) -> dict[str, object]:
    response = client.post("/incidents", json={"title": title})

    assert response.status_code == 201
    assert response.headers["location"] == f"/incidents/{response.json()['id']}"
    return response.json()


def test_incident_crud_and_soft_delete(client: TestClient) -> None:
    created = create_incident(client, "Broken lift")
    incident_id = created["id"]

    assert created["status"] == "OPEN"
    assert created["priority"] == "MEDIUM"

    retrieved = client.get(f"/incidents/{incident_id}")
    assert retrieved.status_code == 200
    assert retrieved.json()["title"] == "Broken lift"

    updated = client.patch(
        f"/incidents/{incident_id}",
        json={
            "description": "Lift is stopped",
            "status": "IN_PROGRESS",
            "priority": "HIGH",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "Lift is stopped"
    assert updated.json()["status"] == "IN_PROGRESS"
    assert updated.json()["priority"] == "HIGH"

    deleted = client.delete(f"/incidents/{incident_id}")
    assert deleted.status_code == 204
    assert deleted.content == b""

    assert client.get(f"/incidents/{incident_id}").status_code == 404
    assert (
        client.patch(
            f"/incidents/{incident_id}", json={"title": "Reopened"}
        ).status_code
        == 404
    )
    assert client.delete(f"/incidents/{incident_id}").status_code == 404


def test_listing_excludes_soft_deleted_incidents(client: TestClient) -> None:
    deleted_incident = create_incident(client, "Deleted incident")
    active_incident = create_incident(client, "Active incident")

    assert client.delete(f"/incidents/{deleted_incident['id']}").status_code == 204

    response = client.get("/incidents")

    assert response.status_code == 200
    assert [incident["id"] for incident in response.json()] == [active_incident["id"]]


def test_incident_api_validates_input_and_missing_records(client: TestClient) -> None:
    assert client.post("/incidents", json={"title": ""}).status_code == 422
    assert client.post("/incidents", json={"title": "   "}).status_code == 422
    assert client.patch("/incidents/999", json={}).status_code == 422
    assert client.get("/incidents/999").status_code == 404
    assert client.get("/incidents/0").status_code == 422
