import io
from typing import Any

from fastapi.testclient import TestClient


def create(client: TestClient, name: str = "Demo ERP") -> dict[str, Any]:
    response = client.post("/projects", json={"name": name})
    assert response.status_code == 201
    body: dict[str, Any] = response.json()
    return body


def test_create_and_list_projects(client: TestClient) -> None:
    project = create(client, "  Demo ERP ")
    assert project["name"] == "Demo ERP"
    assert project["table_count"] == 0
    assert client.get("/projects").json() == [project]


def test_blank_project_name_is_rejected_with_the_error_shape(client: TestClient) -> None:
    response = client.post("/projects", json={"name": "   "})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_INPUT"


def test_csv_upload_creates_a_table(client: TestClient) -> None:
    project = create(client)
    csv = b"KUNNR,NAME1\n0000000001,Alpha\n0000000002,Beta\n"
    response = client.post(
        f"/projects/{project['id']}/tables", files=[("files", ("KNA1.csv", io.BytesIO(csv)))]
    )
    assert response.status_code == 201
    [table] = response.json()
    assert (table["name"], table["row_count"], table["column_count"]) == ("KNA1", 2, 2)
    assert client.get("/projects").json()[0]["table_count"] == 1


def test_unsupported_and_oversized_uploads_are_refused(client: TestClient) -> None:
    project = create(client)
    url = f"/projects/{project['id']}/tables"
    wrong = client.post(url, files=[("files", ("data.xlsx", io.BytesIO(b"x")))])
    assert wrong.status_code == 422
    huge = client.post(url, files=[("files", ("big.csv", io.BytesIO(b"a\n" + b"1\n" * 20_000)))])
    assert huge.status_code == 413
    assert huge.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_sample_dataset_loads_six_tables_and_profiles_them(client: TestClient) -> None:
    project = create(client)
    url = f"/projects/{project['id']}"
    tables = client.post(f"{url}/tables", json={"sample": "erp_s1_sap"}).json()
    assert sorted(t["name"] for t in tables) == ["BSID", "KNA1", "MAKT", "MARA", "VBAK", "VBAP"]
    profile = client.get(f"{url}/profile").json()
    assert {t["table_id"] for t in profile["tables"]} == {t["table_id"] for t in tables}
    overlap = next(
        o for o in profile["overlaps"] if o["from"] == "BSID.KUNNR" and o["to"] == "KNA1.KUNNR"
    )
    assert overlap["normalization"] == "lpad_zeros:10"
    assert profile["keys"][0]["evidence_id"] == "uk_001"
    assert client.get(f"{url}/profile").json() == profile


def test_unknown_samples_and_projects_are_reported(client: TestClient) -> None:
    project = create(client)
    bad = client.post(f"/projects/{project['id']}/tables", json={"sample": "erp_l1_sap"})
    assert bad.status_code == 422
    missing = client.get("/projects/8a5b2c3e-0000-4000-8000-000000000000/profile")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"
    assert client.get("/projects/not-a-uuid/profile").status_code == 422


def test_names_differing_only_by_case_replace_the_same_table(client: TestClient) -> None:
    project = create(client)
    url = f"/projects/{project['id']}/tables"
    client.post(url, files=[("files", ("VBAK.csv", io.BytesIO(b"VBELN\n1\n")))])
    second = client.post(url, files=[("files", ("vbak.csv", io.BytesIO(b"VBELN,X\n1,a\n2,b\n")))])
    assert second.json()[0]["name"] == "VBAK"
    profile = client.get(f"/projects/{project['id']}/profile").json()
    [table] = profile["tables"]
    assert (table["name"], table["row_count"], len(table["columns"])) == ("VBAK", 2, 2)
