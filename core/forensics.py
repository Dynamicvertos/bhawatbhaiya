"""
Digital Forensics & Chain-of-Custody Engine for NCB Field Drug Testing.
Handles SHA-256 image hashing, HMAC cryptographic signing,
QR code generation, and tamper-evident PDF certificate generation.
"""

import hmac
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any
import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors

import config


def generate_image_sha256(image_bytes: bytes) -> str:
    """Computes standard SHA-256 cryptographic digest of the raw image bytes."""
    hasher = hashlib.sha256()
    hasher.update(image_bytes)
    return hasher.hexdigest().upper()


def generate_digital_signature(
    test_id: str,
    timestamp_iso: str,
    operator_id: str,
    image_sha256: str,
    result_category: str
) -> str:
    """
    Generates a cryptographic HMAC-SHA256 signature binding the test metadata
    to the raw image hash using the department secret key.
    """
    payload = f"{test_id}|{timestamp_iso}|{operator_id}|{image_sha256}|{result_category}".encode("utf-8")
    secret = config.SIGNATURE_SECRET.encode("utf-8")
    return hmac.new(secret, payload, hashlib.sha256).hexdigest().upper()


def generate_qr_code_image(verification_url: str, output_path: Path):
    """Generates a QR code image linking to the official verification endpoint."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=2,
    )
    qr.add_data(verification_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0F172A", back_color="white")
    output_path.parent.mkdir(exist_ok=True)
    img.save(str(output_path))


def generate_evidence_certificate(test_data: Dict[str, Any]) -> Path:
    """
    Generates an official-looking tamper-evident PDF certificate for the presumptive test.
    Returns the path to the generated PDF.
    """
    test_id = test_data["test_id_display"]
    pdf_filename = f"Certificate_{test_id}.pdf"
    pdf_path = config.CERTIFICATES_DIR / pdf_filename

    qr_path = config.CERTIFICATES_DIR / f"QR_{test_id}.png"
    verify_url = f"{config.BASE_URL}/verify/{test_id}"
    generate_qr_code_image(verify_url, qr_path)

    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    page_w, page_h = A4

    # Top Header Banner
    c.setFillColor(colors.HexColor("#0F172A")) # Navy Slate
    c.rect(0, page_h - 75, page_w, 75, fill=1, stroke=0)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(40, page_h - 35, "NARCOTICS CONTROL BUREAU - INDIA")
    c.setFont("Helvetica", 9)
    c.drawString(40, page_h - 52, "MINISTRY OF HOME AFFAIRS | FIELD DRUG TESTING DIGITAL COMPANION")

    # Badge/Seal Right
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor("#F59E0B")) # Gold
    c.drawRightString(page_w - 40, page_h - 35, "PRESUMPTIVE TEST RECORD")
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#CBD5E1"))
    c.drawRightString(page_w - 40, page_h - 52, "FORM NDPS-FDT-2026")

    # Document Title
    y = page_h - 105
    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 13)
    c.drawString(40, y, "EVIDENTIARY DIGITAL TEST CERTIFICATE")
    
    # Gold horizontal rule
    c.setStrokeColor(colors.HexColor("#F59E0B"))
    c.setLineWidth(1.5)
    c.line(40, y - 6, page_w - 40, y - 6)

    # 1. Test Metadata Box
    y -= 30
    c.setFillColor(colors.HexColor("#F8FAFC"))
    c.roundRect(40, y - 60, page_w - 80, 60, 4, fill=1, stroke=0)

    c.setFillColor(colors.HexColor("#475569"))
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(55, y - 14, "TEST CERTIFICATE ID")
    c.drawString(200, y - 14, "CASE / CRIME REFERENCE")
    c.drawString(380, y - 14, "NDPS ACT STATUTORY")

    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(55, y - 28, test_data["test_id_display"])
    c.drawString(200, y - 28, str(test_data.get("case_number", f"NCB/FLD/CR-{test_data['test_id_display'].split('-')[-1]}/2026")))
    c.drawString(380, y - 28, str(test_data.get("ndps_section", "Section 21/22 NDPS Act")))

    c.setFillColor(colors.HexColor("#475569"))
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(55, y - 42, "TIMESTAMP (UTC / LOCAL)")
    c.drawString(200, y - 42, "SEIZED QUANTITY")
    c.drawString(380, y - 42, "OPERATOR BADGE ID")

    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(55, y - 54, str(test_data.get("timestamp", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")))[:24])
    c.drawString(200, y - 54, str(test_data.get("seized_quantity", "Presumptive Field Sample"))[:26])
    c.drawString(380, y - 54, str(test_data.get("operator_id", "NCB-OFFICER")))

    # 2. Chemical Analysis Box
    y -= 85
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(40, y, "1. CHEMICAL REAGENT & COLORIMETRIC OUTCOME")

    y -= 14
    res_category = test_data.get("result_category", "INCONCLUSIVE")
    if res_category == "POSITIVE":
        badge_bg = colors.HexColor("#DC2626") # Red
        badge_text = "POSITIVE - CONTROLLED DRUG DETECTED"
    elif res_category == "NEGATIVE":
        badge_bg = colors.HexColor("#16A34A") # Green
        badge_text = "NEGATIVE - UNREACTIVE"
    else:
        badge_bg = colors.HexColor("#D97706") # Amber
        badge_text = "INCONCLUSIVE - LAB CONFIRMATION REQUIRED"

    # Outcome Banner
    c.setFillColor(badge_bg)
    c.roundRect(40, y - 24, page_w - 80, 24, 3, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 10.5)
    c.drawCentredString(page_w / 2.0, y - 16, badge_text)

    # Details table
    y -= 40
    c.setFillColor(colors.HexColor("#1E293B"))
    c.setFont("Helvetica", 8.5)

    labels = [
        ("Reagent Kit Applied:", test_data.get("reagent_name", "Marquis Reagent")),
        ("Target Drug Class:", test_data.get("target_class", test_data.get("target_drug_class", "Opiates / Amphetamines"))),
        ("Detected Substance:", test_data.get("detected_substance", "Heroin Presumptive")),
        ("Packaging / Concealment:", test_data.get("packaging_type", "Sealed evidence packet")),
        ("Confidence Score:", f"{test_data.get('confidence_score', 0.0)}%"),
        ("Scientific Color Distance:", f"CIE Delta E 2000 = {test_data.get('delta_e_metric', 'N/A')} (Tolerance threshold <= 25.0)"),
        ("Lighting Calibration:", test_data.get("calibration_method", "ARUCO_REFERENCE_CARD")),
    ]

    for label, val in labels:
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(colors.HexColor("#475569"))
        c.drawString(55, y, label)
        c.setFont("Helvetica", 8)
        c.setFillColor(colors.HexColor("#0F172A"))
        c.drawString(200, y, str(val))
        y -= 16

    # 3. Geolocation & Scene Context
    y -= 10
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "2. FIELD GEOLOCATION & SCENE CONTEXT")
    y -= 20

    lat = test_data.get("gps_latitude", "N/A")
    lon = test_data.get("gps_longitude", "N/A")
    address = test_data.get("location_address", "Field Operation Site")

    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(colors.HexColor("#475569"))
    c.drawString(55, y, "GPS Coordinates:")
    c.setFont("Helvetica", 8.5)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.drawString(200, y, f"{lat}, {lon}")

    y -= 18
    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(colors.HexColor("#475569"))
    c.drawString(55, y, "Reported Address:")
    c.setFont("Helvetica", 8.5)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.drawString(200, y, str(address)[:65])

    # 4. Chain of Custody & Forensic Hashes
    y -= 30
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "3. TAMPER-EVIDENT CHAIN OF CUSTODY (SHA-256)")
    y -= 15

    c.setFillColor(colors.HexColor("#F1F5F9"))
    c.roundRect(40, y - 85, page_w - 80, 85, 4, fill=1, stroke=0)

    # QR Code on the right
    if qr_path.exists():
        c.drawImage(str(qr_path), page_w - 125, y - 80, width=75, height=75)

    c.setFillColor(colors.HexColor("#334155"))
    c.setFont("Helvetica-Bold", 8)
    c.drawString(55, y - 18, "RAW CAPTURED FRAME SHA-256 HASH:")
    c.setFont("Courier-Bold", 7.5)
    c.setFillColor(colors.HexColor("#0F172A"))
    sha = test_data.get("image_sha256", "E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855")
    c.drawString(55, y - 32, sha[:40])
    c.drawString(55, y - 44, sha[40:])

    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(colors.HexColor("#334155"))
    c.drawString(55, y - 60, "HMAC DIGITAL SIGNATURE:")
    c.setFont("Courier-Bold", 7.5)
    c.setFillColor(colors.HexColor("#0F172A"))
    sig = test_data.get("digital_signature", "UNSIGNED")
    c.drawString(55, y - 72, sig[:50])

    # 5. Statutory Mandatory Note (As requested by NCB Problem Statement)
    y -= 115
    c.setFillColor(colors.HexColor("#FEF3C7")) # Warning Yellow
    c.roundRect(40, y - 45, page_w - 80, 45, 3, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#92400E"))
    c.setFont("Helvetica-Bold", 8)
    c.drawString(55, y - 14, "MANDATORY STATUTORY NOTE (NDPS ACT / NCB PROTOCOL):")
    c.setFont("Helvetica", 7.5)
    c.drawString(55, y - 27, "The output of this digital companion application is a presumptive field-test result and a supporting digital record.")
    c.drawString(55, y - 38, "It establishes probable cause and documentary chain-of-custody. It DOES NOT replace laboratory confirmatory GC-MS testing.")

    # Footer
    c.setFont("Helvetica", 7)
    c.setFillColor(colors.HexColor("#94A3B8"))
    c.drawCentredString(page_w / 2.0, 25, "System-Generated Tamper-Evident Record | Narcotics Control Bureau Field Companion v1.0")

    c.showPage()
    c.save()
    return pdf_path

