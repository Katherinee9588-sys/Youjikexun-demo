from pathlib import Path

from fastapi.testclient import TestClient

from app.integrations.serial_bridge import should_forward_max30102_sample
from app.integrations.serial_protocol import parse_max30102_json_line
from app.main import app
from app.repositories import hardware as hardware_module


client = TestClient(app)


def valid_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "device_id": "max30102-demo-01",
        "sequence": 9,
        "device_uptime_ms": 12340,
        "ir_value": 89321,
        "finger_present": True,
        "heart_rate_bpm": 72.5,
        "spo2_percent": None,
        "signal_quality": "valid",
    }


def test_max30102_sample_is_stored_separately_from_user_entries(
    tmp_path: Path, monkeypatch
) -> None:
    data_path = tmp_path / "hardware_max30102.jsonl"
    monkeypatch.setattr(hardware_module, "DATA_PATH", data_path)

    response = client.post("/api/hardware/max30102/readings", json=valid_payload())

    assert response.status_code == 201
    payload = response.json()
    assert payload["heart_rate_bpm"] == 72.5
    assert payload["spo2_percent"] is None
    assert payload["received_at"].endswith("Z")
    assert data_path.read_text(encoding="utf-8").count("\n") == 1

    latest = client.get("/api/hardware/max30102/latest")
    assert latest.status_code == 200
    assert latest.json()["id"] == payload["id"]


def test_finger_absent_cannot_be_mislabeled_as_a_vital_reading() -> None:
    payload = valid_payload() | {
        "finger_present": False,
        "heart_rate_bpm": 72.5,
        "signal_quality": "finger_absent",
    }

    response = client.post("/api/hardware/max30102/readings", json=payload)

    assert response.status_code == 422


def test_hardware_endpoint_rejects_non_valid_sample() -> None:
    payload = valid_payload() | {
        "heart_rate_bpm": None,
        "signal_quality": "unstable",
    }

    response = client.post("/api/hardware/max30102/readings", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Only signal_quality=valid MAX30102 samples may be stored"
    )


def test_serial_protocol_accepts_ndjson_and_rejects_debug_text() -> None:
    sample = parse_max30102_json_line(
        b'{"schema_version":1,"device_id":"max30102-demo-01","sequence":9,"device_uptime_ms":12340,"ir_value":89321,"finger_present":true,"heart_rate_bpm":72.5,"spo2_percent":null,"signal_quality":"valid"}\n'
    )
    assert sample.device_id == "max30102-demo-01"

    try:
        parse_max30102_json_line(b"IR=89321 | BPM=72.5\n")
    except ValueError as error:
        assert "not valid JSON" in str(error)
    else:
        raise AssertionError("human-only debug text must not be accepted")


def test_serial_bridge_forwards_only_valid_max30102_samples() -> None:
    valid = parse_max30102_json_line(
        b'{"schema_version":1,"device_id":"max30102-demo-01","sequence":9,"device_uptime_ms":12340,"ir_value":89321,"finger_present":true,"heart_rate_bpm":72.5,"spo2_percent":null,"signal_quality":"valid"}\n'
    )
    assert should_forward_max30102_sample(valid) is True

    non_valid_lines = (
        b'{"schema_version":1,"device_id":"max30102-demo-01","sequence":10,"device_uptime_ms":13340,"ir_value":89321,"finger_present":true,"heart_rate_bpm":null,"spo2_percent":null,"signal_quality":"warming_up"}\n',
        b'{"schema_version":1,"device_id":"max30102-demo-01","sequence":11,"device_uptime_ms":14340,"ir_value":89321,"finger_present":true,"heart_rate_bpm":null,"spo2_percent":null,"signal_quality":"unstable"}\n',
        b'{"schema_version":1,"device_id":"max30102-demo-01","sequence":12,"device_uptime_ms":15340,"ir_value":600,"finger_present":false,"heart_rate_bpm":null,"spo2_percent":null,"signal_quality":"finger_absent"}\n',
    )
    for raw_line in non_valid_lines:
        sample = parse_max30102_json_line(raw_line)
        assert should_forward_max30102_sample(sample) is False
