"""
FastAPI Main Application - NCB Digital Companion for Field Drug Testing.
Serves mobile web application, REST APIs, forensic verification, and certificate generation.
"""

import os
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates

import config
from core.color_calibration import process_image_for_colorimetry
from core.reagents import REAGENT_STANDARDS, match_color_against_reagent, rgb_to_hex
from core.forensics import generate_image_sha256, generate_digital_signature, generate_evidence_certificate
from core.database import save_test_record, list_test_records, get_test_record, verify_test_hash, supabase_client

app = FastAPI(
    title="NCB Field Drug Testing Digital Companion",
    description="Presumptive Colorimetric Calibration & Evidentiary Chain-of-Custody (NDPS Act)",
    version="1.0.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static and Templates
app.mount("/static", StaticFiles(directory=str(config.BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(config.BASE_DIR / "templates"))


@app.get("/", response_class=HTMLResponse)
async def serve_index(request: Request):
    """Serves the main mobile-first web app."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "supabase_connected": supabase_client is not None,
            "base_url": config.BASE_URL
        }
    )


@app.get("/manifest.json")
async def get_manifest():
    """Serves the Progressive Web App (PWA) Web App Manifest."""
    manifest_path = config.BASE_DIR / "static" / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Manifest not found")
    return FileResponse(manifest_path, media_type="application/manifest+json")


@app.get("/sw.js")
async def get_service_worker():
    """Serves the Progressive Web App (PWA) Service Worker with root scope permissions."""
    sw_path = config.BASE_DIR / "static" / "sw.js"
    if not sw_path.exists():
        raise HTTPException(status_code=404, detail="Service worker not found")
    response = FileResponse(sw_path, media_type="application/javascript")
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/favicon.ico")
async def get_favicon():
    """Serves the favicon icon."""
    favicon_path = config.BASE_DIR / "static" / "icons" / "favicon.png"
    if favicon_path.exists():
        return FileResponse(favicon_path, media_type="image/png")
    return JSONResponse(status_code=204, content={})


@app.get("/api/wifi-qr")
async def get_wifi_qr(request: Request):
    """Generates a dynamic QR code for Android phone camera to easily open the web app over local Wi-Fi or Cloud."""
    import socket, qrcode, io
    from fastapi.responses import Response

    host_header = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    proto = request.headers.get("x-forwarded-proto") or ("https" if "render.com" in host_header else "http")

    if "render.com" in host_header or "bhawatbhaiya" in host_header:
        target_url = f"{proto}://{host_header}"
    elif config.BASE_URL and "render.com" in config.BASE_URL:
        target_url = config.BASE_URL
    else:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('8.8.8.8', 80))
            local_ip = s.getsockname()[0]
        except Exception:
            local_ip = '127.0.0.1'
        finally:
            s.close()
        target_url = f"http://{local_ip}:{config.PORT}"

    qr_img = qrcode.make(target_url)
    buf = io.BytesIO()
    qr_img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


@app.get("/download/apk")
async def download_apk():
    """Serves the standalone signed Android APK file for download and direct sideloading."""
    apk_path = config.BASE_DIR / "NCB-SPECTRA.apk"
    if not apk_path.exists():
        raise HTTPException(status_code=404, detail="APK file not found")
    return FileResponse(
        apk_path,
        media_type="application/vnd.android.package-archive",
        filename="NCB-SPECTRA.apk"
    )


@app.get("/verify/{test_id}", response_class=HTMLResponse)
async def verify_certificate_page(request: Request, test_id: str):
    """Public verification page triggered when someone scans the QR code on a PDF certificate."""
    record = get_test_record(test_id)
    return templates.TemplateResponse(
        request=request,
        name="verify.html",
        context={
            "test": record,
            "test_id": test_id
        }
    )


@app.get("/health")
def health_check():
    """System health check and database connection status."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database_backend": "Supabase PostgreSQL" if supabase_client is not None else "Local SQLite Fallback",
        "version": "1.0.0",
        "theme": "MedTech / BioTech / Digital Forensics"
    }


@app.get("/api/reagents")
def get_reagents():
    """Returns the list of supported presumptive reagent kits."""
    return list(REAGENT_STANDARDS.values())


@app.post("/api/test/analyze")
async def analyze_drug_test(
    image: UploadFile = File(...),
    reagent_id: str = Form("marquis"),
    operator_id: str = Form("NCB-DEL-7491"),
    operator_name: str = Form("Field Officer"),
    case_number: Optional[str] = Form(None),
    ndps_section: Optional[str] = Form(None),
    seized_quantity: Optional[str] = Form(None),
    packaging_type: Optional[str] = Form(None),
    witness_panchanama: Optional[str] = Form(None),
    gps_latitude: Optional[float] = Form(None),
    gps_longitude: Optional[float] = Form(None),
    location_address: Optional[str] = Form("Field Seizure Location"),
    device_info: Optional[str] = Form("Mobile Companion Browser")
):
    """
    Main Presumptive Analysis Endpoint:
    1. Reads raw image bytes and computes cryptographic SHA-256 hash.
    2. Executes OpenCV color constancy calibration (ArUco reference card / White Balance).
    3. Analyzes sample color against standard chemical reagent spectra (CIE Delta E).
    4. Generates HMAC digital signature and signed PDF certificate with QR code.
    5. Saves record to Supabase (or SQLite fallback) and returns evidentiary JSON.
    """
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty image uploaded.")

    # 1. Forensic Hash of RAW frame immediately
    raw_sha256 = generate_image_sha256(image_bytes)

    # 2. Computer Vision Color Calibration Pipeline
    try:
        cv_result = process_image_for_colorimetry(image_bytes)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Image processing error: {str(e)}")

    calibrated_rgb = cv_result["calibrated_rgb"]
    raw_rgb = cv_result["raw_rgb"]

    # 3. Chemical Colorimetry Matcher
    try:
        match_result = match_color_against_reagent(calibrated_rgb, reagent_id)
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))

    # 4. Generate Unique Test Display ID and Legal NDPS Metadata
    random_suffix = random.randint(1000, 9999)
    test_id_display = f"NCB-{datetime.now().year}-FDT-{random_suffix}"
    timestamp_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Legal case mapping based on reagent and result
    if not case_number or not case_number.strip():
        case_number = f"NCB/FLD/CR-{random_suffix}/2026"

    if not ndps_section or not ndps_section.strip():
        if match_result["result_category"] == "POSITIVE":
            if reagent_id in ["marquis", "scott"]:
                ndps_section = "Section 21(c) NDPS Act, 1985 (Commercial Quantity)"
            elif reagent_id == "duquenois_levine":
                ndps_section = "Section 20(b)(ii) NDPS Act, 1985 (Cannabis Seizure)"
            else:
                ndps_section = "Section 22(c) NDPS Act, 1985 (Psychotropic Substances)"
        else:
            ndps_section = "Exempt - Negative Field Verification (Suspected Sample Cleared)"

    if not seized_quantity or not seized_quantity.strip():
        seized_quantity = "250.0 grams (Field Presumptive)" if match_result["result_category"] == "POSITIVE" else "Clean / Negative Sample"

    if not packaging_type or not packaging_type.strip():
        packaging_type = "Heat-sealed evidence container"

    if not witness_panchanama or not witness_panchanama.strip():
        witness_panchanama = "Executed under Sec 50 NDPS in presence of 2 independent witnesses"

    # 5. Cryptographic Digital Signature
    digital_signature = generate_digital_signature(
        test_id=test_id_display,
        timestamp_iso=timestamp_iso,
        operator_id=operator_id,
        image_sha256=raw_sha256,
        result_category=match_result["result_category"]
    )

    # Construct test data dictionary
    test_data = {
        "test_id_display": test_id_display,
        "case_number": case_number,
        "ndps_section": ndps_section,
        "seized_quantity": seized_quantity,
        "packaging_type": packaging_type,
        "witness_panchanama": witness_panchanama,
        "timestamp": timestamp_iso,
        "operator_id": operator_id,
        "operator_name": operator_name,
        "reagent_id": match_result["reagent_id"],
        "reagent_name": match_result["reagent_name"],
        "target_class": match_result["target_class"],
        "target_drug_class": match_result["target_class"],
        "detected_substance": match_result["detected_substance"],
        "result_category": match_result["result_category"],
        "confidence_score": match_result["confidence_score"],
        "delta_e_metric": match_result["delta_e_metric"],
        "explanation": match_result["explanation"],
        "calibration_method": cv_result["calibration_method"],
        "card_detected": cv_result["card_detected"],
        "raw_sample_hex": rgb_to_hex(raw_rgb),
        "calibrated_sample_hex": rgb_to_hex(calibrated_rgb),
        "expected_standard_hex": match_result["expected_hex"],
        "image_sha256": raw_sha256,
        "digital_signature": digital_signature,
        "gps_latitude": gps_latitude or 28.6139, # Default Delhi coords if permission denied
        "gps_longitude": gps_longitude or 77.2090,
        "location_address": location_address or "New Delhi, India (Field Site)",
        "device_info": device_info
    }

    # 6. Generate Official Tamper-Evident Evidence Certificate (PDF)
    try:
        pdf_path = generate_evidence_certificate(test_data)
        pdf_bytes = open(pdf_path, "rb").read() if pdf_path.exists() else None
    except Exception as pdf_err:
        print(f"[CERTIFICATE WARNING] PDF generation note: {pdf_err}")
        pdf_bytes = None

    # 7. Persist to Database (Supabase Cloud or SQLite fallback)
    saved_record = save_test_record(test_data, image_bytes, pdf_bytes)

    return {
        "success": True,
        "message": "Field drug test analyzed and cryptographically recorded successfully.",
        "record": saved_record,
        "cv_meta": {
            "card_detected": cv_result["card_detected"],
            "status_note": cv_result["status_note"],
            "raw_rgb": raw_rgb,
            "calibrated_rgb": calibrated_rgb
        }
    }


@app.get("/api/tests")
def get_all_tests(
    query: Optional[str] = None,
    reagent_id: Optional[str] = "ALL",
    result_category: Optional[str] = "ALL",
    limit: int = 50,
    offset: int = 0
):
    """Retrieves searchable logs of tests conducted with filters."""
    records = list_test_records(
        query=query,
        reagent_id=reagent_id,
        result_category=result_category,
        limit=limit,
        offset=offset
    )
    return {"count": len(records), "records": records}


@app.get("/api/test/{test_id}")
def get_single_test(test_id: str):
    """Fetches details of a specific test record."""
    record = get_test_record(test_id)
    if not record:
        raise HTTPException(status_code=404, detail="Test record not found.")
    return record


@app.get("/api/test/{test_id}/certificate")
def download_certificate(test_id: str):
    """Serves the generated PDF certificate."""
    pdf_path = config.CERTIFICATES_DIR / f"Certificate_{test_id}.pdf"
    if not pdf_path.exists():
        # Try regenerating if record exists
        record = get_test_record(test_id)
        if record:
            pdf_path = generate_evidence_certificate(record)
        else:
            raise HTTPException(status_code=404, detail="Certificate not found.")

    return FileResponse(
        path=str(pdf_path),
        filename=f"NCB_Evidence_Certificate_{test_id}.pdf",
        media_type="application/pdf"
    )


@app.get("/api/test/{test_id}/image")
def get_test_image(test_id: str):
    """Serves the captured sample image."""
    image_path = config.UPLOADS_DIR / f"{test_id}_sample.jpg"
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image file not found.")
    return FileResponse(path=str(image_path), media_type="image/jpeg")


@app.get("/api/verify-hash")
def verify_hash_endpoint(q: str = Query(..., description="Raw SHA-256 Hash or Test ID")):
    """Verifies evidence authenticity against the cryptographic record."""
    record = verify_test_hash(q)
    if not record:
        return {
            "verified": False,
            "message": "NO MATCH FOUND. This record or hash is not registered in the NCB official chain-of-custody ledger."
        }
    return {
        "verified": True,
        "message": "AUTHENTIC RECORD VERIFIED. Cryptographic hash matches the original seized field test frame.",
        "record": record
    }


@app.get("/api/reference-card/pdf")
def download_reference_card_pdf():
    """Downloads the printable A4 reference card PDF."""
    pdf_path = config.DATA_DIR / "reference_card.pdf"
    if not pdf_path.exists():
        from generate_reference_card import build_card_pdf
        build_card_pdf()
    return FileResponse(path=str(pdf_path), filename="NCB_Calibration_Card_FDT_C1.pdf", media_type="application/pdf")


@app.get("/api/reference-card/png")
def download_reference_card_png():
    """Downloads the reference card PNG."""
    png_path = config.DATA_DIR / "reference_card.png"
    if not png_path.exists():
        from generate_reference_card import build_card_pdf
        build_card_pdf()
    return FileResponse(path=str(png_path), filename="NCB_Calibration_Card_FDT_C1.png", media_type="image/png")


@app.get("/api/demo-sample/{sample_name}")
def get_demo_sample(sample_name: str):
    """Serves high-res pre-calibrated sample card images for instant live demo testing."""
    sample_file = config.DATA_DIR / "demo_samples" / f"{sample_name}_sample.jpg"
    if not sample_file.exists():
        from generate_reference_card import generate_all_demo_samples
        generate_all_demo_samples()
    if not sample_file.exists():
        raise HTTPException(status_code=404, detail="Demo sample card not found.")
    return FileResponse(path=str(sample_file), media_type="image/jpeg")

