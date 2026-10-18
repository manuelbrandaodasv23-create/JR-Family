from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def register(email, name="Pessoa"):
    r = client.post("/auth/register", json={"name": name, "email": email, "password": "senha-segura-123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_family_device_location_and_idor_block():
    guardian = register("guardiao@example.com", "Responsável")
    outsider = register("fora@example.com", "Fora")

    r = client.post("/families", headers=guardian, json={"name": "Família Teste"})
    assert r.status_code == 200
    family_id = r.json()["id"]
    member_id = r.json()["member_id"]

    r = client.post(
        f"/families/{family_id}/devices",
        headers=guardian,
        json={"member_id": member_id, "platform": "android", "device_name": "Pixel Teste"},
    )
    assert r.status_code == 200
    device_id = r.json()["id"]

    r = client.patch(
        f"/families/{family_id}/devices/{device_id}/permissions",
        headers=guardian,
        json={"location": "authorized", "background": "authorized", "sharing_enabled": True},
    )
    assert r.status_code == 200

    r = client.post(
        f"/devices/{device_id}/locations",
        headers=guardian,
        json={"latitude": -8.7612, "longitude": -63.9004, "battery_percent": 50, "source_mode": "balanced"},
    )
    assert r.status_code == 200, r.text

    r = client.get(f"/families/{family_id}/members/{member_id}/location/latest", headers=guardian)
    assert r.status_code == 200
    assert r.json()["location"]["latitude"] == -8.7612

    r = client.get(f"/families/{family_id}/members/{member_id}/location/latest", headers=outsider)
    assert r.status_code == 403
