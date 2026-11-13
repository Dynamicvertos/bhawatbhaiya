"""
End-to-End Test Suite for NCB Field Drug Testing Digital Companion.
Tests API routes, colorimetric calibration, hashing, and database queries.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient
from main import app
import cv2
import numpy as np

client = TestClient(app)

def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    print("[PASS] Health Check:", data["database_backend"])

def test_reagents():
    res = client.get("/api/reagents")
    assert res.status_code == 200
    reagents = res.json()
    assert len(reagents) >= 5
    ids = [r["id"] for r in reagents]
    assert "marquis" in ids
    assert "scott" in ids
    print(f"[PASS] Reagents Endpoint ({len(reagents)} kits loaded: {', '.join(ids)})")

def test_list_tests():
    res = client.get("/api/tests")
    assert res.status_code == 200
    data = res.json()
    assert data["count"] >= 3
    print(f"[PASS] List Tests ({data['count']} records found in audit log)")

def test_hash_verification():
    res = client.get("/api/verify-hash?q=NCB-2026-FDT-9821")
    assert res.status_code == 200
    data = res.json()
    assert data["verified"] is True
    assert data["record"]["test_id_display"] == "NCB-2026-FDT-9821"
    print("[PASS] Hash & Chain-of-Custody Verification")

def test_analyze_with_reference_card():
    card_path = Path(__file__).resolve().parent / "data" / "reference_card.png"
    assert card_path.exists(), "Reference card must exist"
    
    with open(card_path, "rb") as f:
        file_bytes = f.read()

    res = client.post(
        "/api/test/analyze",
        data={
            "reagent_id": "marquis",
            "operator_id": "NCB-TEST-007",
            "operator_name": "Test Agent",
            "gps_latitude": 28.6139,
            "gps_longitude": 77.2090,
            "location_address": "Test Lab HQ, New Delhi"
        },
        files={
            "image": ("card.png", file_bytes, "image/png")
        }
    )
    assert res.status_code == 200, f"Analysis failed: {res.text}"
    data = res.json()
    assert data["success"] is True
    rec = data["record"]
    assert rec["calibration_method"] == "ARUCO_REFERENCE_CARD"
    assert rec["card_detected"] is True
    assert len(rec["image_sha256"]) == 64
    print(f"[PASS] Full Image Analysis (Test ID: {rec['test_id_display']}, Method: {rec['calibration_method']}, SHA: {rec['image_sha256'][:16]}...)")

if __name__ == "__main__":
    print("Running E2E System Test Suite...")
    test_health()
    test_reagents()
    test_list_tests()
    test_hash_verification()
    test_analyze_with_reference_card()
    print("\nALL 5 SYSTEM TESTS PASSED SUCCESSFULLY! [OK]")
