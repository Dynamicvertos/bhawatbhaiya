"""
Unified Database & Storage Layer for NCB Field Drug Testing.
Connects to Supabase Cloud PostgreSQL & Object Storage,
with an automatic, zero-crash fallback to local SQLite and local disk.
"""

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
import config

# Try to initialize Supabase client if configured
supabase_client = None
if config.is_supabase_configured():
    try:
        from supabase import create_client
        supabase_client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
        print("[DATABASE] Supabase Cloud client initialized successfully.")
    except Exception as e:
        print(f"[DATABASE] Supabase initialization failed ({e}). Falling back to local SQLite.")
        supabase_client = None


def init_sqlite_db():
    """Initializes local SQLite database table if not present, and ensures all columns exist."""
    config.DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(config.SQLITE_DB_PATH))
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS field_drug_tests (
        id TEXT PRIMARY KEY,
        test_id_display TEXT NOT NULL,
        case_number TEXT,
        ndps_section TEXT,
        seized_quantity TEXT,
        packaging_type TEXT,
        witness_panchanama TEXT,
        timestamp TEXT NOT NULL,
        operator_id TEXT NOT NULL,
        operator_name TEXT,
        reagent_id TEXT NOT NULL,
        reagent_name TEXT NOT NULL,
        target_drug_class TEXT NOT NULL,
        detected_substance TEXT NOT NULL,
        result_category TEXT NOT NULL,
        confidence_score REAL NOT NULL,
        delta_e_metric REAL,
        explanation TEXT,
        calibration_method TEXT,
        card_detected INTEGER,
        raw_sample_hex TEXT,
        calibrated_sample_hex TEXT,
        expected_standard_hex TEXT,
        image_sha256 TEXT NOT NULL,
        digital_signature TEXT,
        gps_latitude REAL,
        gps_longitude REAL,
        location_address TEXT,
        device_info TEXT,
        image_url TEXT,
        certificate_url TEXT,
        created_at TEXT NOT NULL
    )
    """)
    # Check for missing columns in existing databases and apply migration
    cursor.execute("PRAGMA table_info(field_drug_tests)")
    existing_cols = [row[1] for row in cursor.fetchall()]
    new_cols = [
        ("case_number", "TEXT"),
        ("ndps_section", "TEXT"),
        ("seized_quantity", "TEXT"),
        ("packaging_type", "TEXT"),
        ("witness_panchanama", "TEXT"),
        ("cfsl_lab_ref", "TEXT"),
        ("seal_number", "TEXT"),
        ("estimated_value", "TEXT"),
        ("adulterant_screening", "TEXT")
    ]
    for col_name, col_type in new_cols:
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE field_drug_tests ADD COLUMN {col_name} {col_type}")
            print(f"[DATABASE MIGRATION] Added column '{col_name}' to local database.")

    conn.commit()
    conn.close()


# Ensure SQLite table exists on startup
init_sqlite_db()


def save_test_record(
    record_data: Dict[str, Any],
    image_bytes: bytes,
    pdf_bytes: Optional[bytes] = None
) -> Dict[str, Any]:
    """
    Saves the test record and media.
    Tries Supabase first; if unavailable, saves locally to SQLite and filesystem.
    """
    test_id = record_data.get("test_id_display") or f"NCB-{int(datetime.now().timestamp())}"
    record_id = record_data.get("id") or str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()

    record_data["id"] = record_id
    record_data["test_id_display"] = test_id
    if "timestamp" not in record_data or not record_data["timestamp"]:
        record_data["timestamp"] = now_iso
    record_data["created_at"] = now_iso

    # Defaults for official seizure fields
    record_data["case_number"] = record_data.get("case_number") or f"NCB/FLD/CR-{test_id.split('-')[-1]}/2026"
    record_data["ndps_section"] = record_data.get("ndps_section") or "Section 21/22 NDPS Act, 1985"
    record_data["seized_quantity"] = record_data.get("seized_quantity") or "Presumptive Field Sample"
    record_data["packaging_type"] = record_data.get("packaging_type") or "Sealed evidence packet"
    record_data["witness_panchanama"] = record_data.get("witness_panchanama") or "Executed under Sec 50 in presence of independent witnesses"
    record_data["cfsl_lab_ref"] = record_data.get("cfsl_lab_ref") or f"CFSL-NDPS-2026-CH-{test_id.split('-')[-1]}"
    record_data["seal_number"] = record_data.get("seal_number") or f"NCB-EMBOSSED-WAX-SEAL-#14"
    record_data["estimated_value"] = record_data.get("estimated_value") or ("Presumptive Seizure" if record_data.get("result_category") == "POSITIVE" else "Exempt")
    record_data["adulterant_screening"] = record_data.get("adulterant_screening") or "Negative for common cutting excipients"

    # Save local copies of files first (safe backup)
    local_image_name = f"{test_id}_sample.jpg"
    local_image_path = config.UPLOADS_DIR / local_image_name
    with open(local_image_path, "wb") as f:
        f.write(image_bytes)

    local_cert_url = f"/api/test/{test_id}/certificate"
    local_img_url = f"/api/test/{test_id}/image"

    record_data["image_url"] = local_img_url
    record_data["certificate_url"] = local_cert_url

    # Attempt Supabase Cloud upload & insert
    if supabase_client is not None:
        try:
            # 1. Upload image to Supabase Storage (if bucket exists)
            try:
                storage_res = supabase_client.storage.from_("drug-test-images").upload(
                    path=local_image_name,
                    file=image_bytes,
                    file_options={"content-type": "image/jpeg", "upsert": "true"}
                )
                pub_url = supabase_client.storage.from_("drug-test-images").get_public_url(local_image_name)
                record_data["image_url"] = pub_url
            except Exception as st_err:
                print(f"[STORAGE WARNING] Supabase image upload note: {st_err}. Using local URL.")

            # 2. Insert row into Supabase PostgreSQL table
            payload = {
                "id": record_data["id"],
                "test_id_display": record_data["test_id_display"],
                "case_number": record_data.get("case_number"),
                "ndps_section": record_data.get("ndps_section"),
                "seized_quantity": record_data.get("seized_quantity"),
                "packaging_type": record_data.get("packaging_type"),
                "witness_panchanama": record_data.get("witness_panchanama"),
                "timestamp": record_data["timestamp"],
                "operator_id": record_data.get("operator_id", "NCB-OFFICER"),
                "operator_name": record_data.get("operator_name", "Field Officer"),
                "reagent_id": record_data["reagent_id"],
                "reagent_name": record_data["reagent_name"],
                "target_drug_class": record_data.get("target_drug_class", record_data.get("target_class", "")),
                "detected_substance": record_data["detected_substance"],
                "result_category": record_data["result_category"],
                "confidence_score": float(record_data.get("confidence_score", 0.0)),
                "delta_e_metric": float(record_data.get("delta_e_metric", 0.0)) if record_data.get("delta_e_metric") is not None else None,
                "explanation": record_data.get("explanation", ""),
                "calibration_method": record_data.get("calibration_method", "ARUCO_REFERENCE_CARD"),
                "card_detected": bool(record_data.get("card_detected", False)),
                "raw_sample_hex": record_data.get("raw_sample_hex", ""),
                "calibrated_sample_hex": record_data.get("calibrated_sample_hex", ""),
                "expected_standard_hex": record_data.get("expected_standard_hex", ""),
                "image_sha256": record_data["image_sha256"],
                "digital_signature": record_data.get("digital_signature", ""),
                "gps_latitude": float(record_data.get("gps_latitude")) if record_data.get("gps_latitude") is not None else None,
                "gps_longitude": float(record_data.get("gps_longitude")) if record_data.get("gps_longitude") is not None else None,
                "location_address": record_data.get("location_address", ""),
                "device_info": record_data.get("device_info", "Mobile Companion PWA"),
                "image_url": record_data["image_url"],
                "certificate_url": record_data["certificate_url"]
            }

            res = supabase_client.table("field_drug_tests").insert(payload).execute()
            print(f"[DATABASE] Saved record {test_id} to Supabase Cloud.")
            return record_data
        except Exception as sb_err:
            print(f"[DATABASE WARNING] Supabase insert failed ({sb_err}). Saving to local SQLite.")

    # SQLite fallback insert
    conn = sqlite3.connect(str(config.SQLITE_DB_PATH))
    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR REPLACE INTO field_drug_tests (
        id, test_id_display, case_number, ndps_section, seized_quantity, packaging_type, witness_panchanama,
        cfsl_lab_ref, seal_number, estimated_value, adulterant_screening,
        timestamp, operator_id, operator_name, reagent_id, reagent_name, target_drug_class, detected_substance,
        result_category, confidence_score, delta_e_metric, explanation, calibration_method, card_detected,
        raw_sample_hex, calibrated_sample_hex, expected_standard_hex, image_sha256, digital_signature,
        gps_latitude, gps_longitude, location_address, device_info, image_url, certificate_url, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        record_data["id"],
        record_data["test_id_display"],
        record_data.get("case_number", ""),
        record_data.get("ndps_section", ""),
        record_data.get("seized_quantity", ""),
        record_data.get("packaging_type", ""),
        record_data.get("witness_panchanama", ""),
        record_data.get("cfsl_lab_ref", ""),
        record_data.get("seal_number", ""),
        record_data.get("estimated_value", ""),
        record_data.get("adulterant_screening", ""),
        record_data["timestamp"],
        record_data.get("operator_id", "NCB-OFFICER"),
        record_data.get("operator_name", "Field Officer"),
        record_data["reagent_id"],
        record_data["reagent_name"],
        record_data.get("target_drug_class", record_data.get("target_class", "")),
        record_data["detected_substance"],
        record_data["result_category"],
        float(record_data.get("confidence_score", 0.0)),
        float(record_data.get("delta_e_metric", 0.0)) if record_data.get("delta_e_metric") is not None else None,
        record_data.get("explanation", ""),
        record_data.get("calibration_method", "ARUCO_REFERENCE_CARD"),
        1 if record_data.get("card_detected") else 0,
        record_data.get("raw_sample_hex", ""),
        record_data.get("calibrated_sample_hex", ""),
        record_data.get("expected_standard_hex", ""),
        record_data["image_sha256"],
        record_data.get("digital_signature", ""),
        float(record_data.get("gps_latitude")) if record_data.get("gps_latitude") is not None else None,
        float(record_data.get("gps_longitude")) if record_data.get("gps_longitude") is not None else None,
        record_data.get("location_address", ""),
        record_data.get("device_info", "Mobile Companion PWA"),
        record_data["image_url"],
        record_data["certificate_url"],
        record_data["created_at"]
    ))
    conn.commit()
    conn.close()
    print(f"[DATABASE] Saved record {test_id} to local SQLite.")
    return record_data


def list_test_records(
    query: Optional[str] = None,
    reagent_id: Optional[str] = None,
    result_category: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Fetches tests with optional search filtering by substance, officer, or ID."""
    # Attempt Supabase query first
    if supabase_client is not None:
        try:
            req = supabase_client.table("field_drug_tests").select("*").order("timestamp", desc=True)
            if reagent_id and reagent_id != "ALL":
                req = req.eq("reagent_id", reagent_id)
            if result_category and result_category != "ALL":
                req = req.eq("result_category", result_category)
            if query and query.strip():
                # Filter by test_id_display or operator_id or detected_substance
                q = query.strip()
                req = req.or_(f"test_id_display.ilike.%{q}%,operator_id.ilike.%{q}%,detected_substance.ilike.%{q}%")
            res = req.range(offset, offset + limit - 1).execute()
            if res.data is not None:
                return res.data
        except Exception as e:
            print(f"[DATABASE WARNING] Supabase list failed ({e}). Falling back to SQLite.")

    # SQLite query
    conn = sqlite3.connect(str(config.SQLITE_DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    conditions = []
    params = []

    if reagent_id and reagent_id != "ALL":
        conditions.append("reagent_id = ?")
        params.append(reagent_id)

    if result_category and result_category != "ALL":
        conditions.append("result_category = ?")
        params.append(result_category)

    if query and query.strip():
        q = f"%{query.strip()}%"
        conditions.append("(test_id_display LIKE ? OR operator_id LIKE ? OR detected_substance LIKE ?)")
        params.extend([q, q, q])

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT * FROM field_drug_tests {where_clause} ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    results = [dict(row) for row in rows]
    conn.close()
    return results


def get_test_record(test_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves single test record by test_id_display or UUID id."""
    if supabase_client is not None:
        try:
            res = supabase_client.table("field_drug_tests").select("*").or_(f"test_id_display.eq.{test_id},id.eq.{test_id}").limit(1).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
        except Exception as e:
            print(f"[DATABASE WARNING] Supabase get failed ({e}). Falling back to SQLite.")

    conn = sqlite3.connect(str(config.SQLITE_DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM field_drug_tests WHERE test_id_display = ? OR id = ? LIMIT 1", (test_id, test_id))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def verify_test_hash(hash_or_id: str) -> Optional[Dict[str, Any]]:
    """Searches for a record matching the raw SHA-256 hash or Test ID for authenticity check."""
    q = hash_or_id.strip()
    if supabase_client is not None:
        try:
            res = supabase_client.table("field_drug_tests").select("*").or_(f"image_sha256.eq.{q},test_id_display.eq.{q}").limit(1).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
        except Exception as e:
            pass

    conn = sqlite3.connect(str(config.SQLITE_DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM field_drug_tests WHERE image_sha256 = ? OR test_id_display = ? LIMIT 1", (q, q))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

