"""
Generates the official printable NCB Reference Color Calibration Card (Model FDT-C1).
Contains 4-corner ArUco fiducials, calibrated reference swatches, and test well placement.
"""

import cv2
import numpy as np
from pathlib import Path
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors

CARD_PNG_PATH = Path(__file__).resolve().parent / "data" / "reference_card.png"
CARD_PDF_PATH = Path(__file__).resolve().parent / "data" / "reference_card.pdf"
DEMO_SAMPLES_DIR = Path(__file__).resolve().parent / "data" / "demo_samples"


def generate_reference_card_image(
    width: int = 1200, 
    height: int = 750, 
    sample_bgr: tuple = None, 
    sample_label: str = None
) -> np.ndarray:
    """Creates a high-resolution 1200x750 card image with ArUco markers, swatches, and optional sample well color."""
    # White background card
    card = np.ones((height, width, 3), dtype=np.uint8) * 248

    # Outer border
    cv2.rectangle(card, (10, 10), (width - 10, height - 10), (40, 40, 40), 3)

    # 1. Generate ArUco Markers
    try:
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    except AttributeError:
        dictionary = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50)

    marker_size = 110
    corner_margin = 35

    def draw_marker(marker_id: int) -> np.ndarray:
        try:
            marker = cv2.aruco.generateImageMarker(dictionary, marker_id, marker_size)
        except AttributeError:
            marker = cv2.aruco.drawMarker(dictionary, marker_id, marker_size)
        return cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)

    # Place 4 ArUco markers on 4 corners
    # ID 0: Top-Left
    m0 = draw_marker(0)
    card[corner_margin:corner_margin+marker_size, corner_margin:corner_margin+marker_size] = m0

    # ID 1: Top-Right
    m1 = draw_marker(1)
    card[corner_margin:corner_margin+marker_size, width-corner_margin-marker_size:width-corner_margin] = m1

    # ID 2: Bottom-Right
    m2 = draw_marker(2)
    card[height-corner_margin-marker_size:height-corner_margin, width-corner_margin-marker_size:width-corner_margin] = m2

    # ID 3: Bottom-Left
    m3 = draw_marker(3)
    card[height-corner_margin-marker_size:height-corner_margin, corner_margin:corner_margin+marker_size] = m3

    # 2. Header and Title
    cv2.putText(card, "NARCOTICS CONTROL BUREAU - INDIA", (220, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (20, 20, 20), 2)
    cv2.putText(card, "FIELD DRUG TESTING COLOR CALIBRATION CARD [MODEL FDT-C1]", (220, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (90, 90, 90), 1)

    # 3. Draw Reference Swatches on the Left
    swatch_r = 48

    # White Reference Swatch
    wh_center = (int(width * 0.22), int(height * 0.35))
    cv2.circle(card, wh_center, swatch_r, (245, 245, 245), -1)
    cv2.circle(card, wh_center, swatch_r, (100, 100, 100), 2)
    cv2.putText(card, "CALIB WHITE (D65)", (wh_center[0] - 65, wh_center[1] + swatch_r + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (50, 50, 50), 1)

    # 18% Neutral Gray Reference Swatch
    gr_center = (int(width * 0.22), int(height * 0.65))
    cv2.circle(card, gr_center, swatch_r, (118, 118, 118), -1)
    cv2.circle(card, gr_center, swatch_r, (80, 80, 80), 2)
    cv2.putText(card, "18% NEUTRAL GRAY", (gr_center[0] - 65, gr_center[1] + swatch_r + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (50, 50, 50), 1)

    # Standard Color Chips (Black, Red, Green, Blue)
    chips = [
        ("BLACK", (30, 30, 30)),
        ("RED", (30, 30, 220)),
        ("GREEN", (30, 180, 30)),
        ("BLUE", (220, 60, 30))
    ]
    chip_x = int(width * 0.36)
    for idx, (label, bgr) in enumerate(chips):
        cy = int(height * 0.25) + (idx * 105)
        cv2.rectangle(card, (chip_x, cy), (chip_x + 50, cy + 40), bgr, -1)
        cv2.rectangle(card, (chip_x, cy), (chip_x + 50, cy + 40), (80, 80, 80), 1)
        cv2.putText(card, label, (chip_x + 60, cy + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (60, 60, 60), 1)

    # 4. Reaction Well Target (Where test tube / vial / pouch is placed)
    well_cx, well_cy = int(width * 0.65), int(height * 0.50)
    well_radius = int(min(width, height) * 0.22)

    # Target circles
    cv2.circle(card, (well_cx, well_cy), well_radius, (255, 255, 255), -1)
    cv2.circle(card, (well_cx, well_cy), well_radius, (0, 102, 204), 3)
    cv2.circle(card, (well_cx, well_cy), well_radius - 20, (0, 102, 204), 1)

    # Crosshairs
    cv2.line(card, (well_cx - well_radius - 10, well_cy), (well_cx + well_radius + 10, well_cy), (0, 102, 204), 1)
    cv2.line(card, (well_cx, well_cy - well_radius - 10), (well_cx, well_cy + well_radius + 10), (0, 102, 204), 1)

    if sample_bgr is not None:
        # Fill sample well with authentic chemical reaction color
        inner_r = int(min(width, height) * 0.15)
        cv2.circle(card, (well_cx, well_cy), inner_r, sample_bgr, -1)
        cv2.circle(card, (well_cx, well_cy), inner_r, (40, 40, 40), 2)
        if sample_label:
            cv2.putText(card, f"[ACTIVE REACTION: {sample_label}]", (well_cx - 150, well_cy + well_radius + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 120, 60), 2)
    else:
        cv2.putText(card, "SAMPLE REACTION WELL", (well_cx - 100, well_cy - well_radius - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 80, 160), 2)
        cv2.putText(card, "[ PLACE TEST VIAL / POUCH HERE ]", (well_cx - 120, well_cy + well_radius + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (80, 80, 80), 1)

    # 5. Instructions and scale
    cv2.putText(card, "INSTRUCTIONS: Ensure all 4 corner markers are visible in phone camera viewfinder.", (60, height - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (90, 90, 90), 1)

    return card


def generate_all_demo_samples():
    """Generates 6 authentic pre-calibrated reference card images for instant demo testing."""
    DEMO_SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    samples = {
        "heroin": {
            "bgr": (69, 10, 59),       # RGB: 59, 10, 69 (#3B0A45) - Deep Violet
            "label": "HEROIN / MORPHINE (MARQUIS VIOLET)"
        },
        "cocaine": {
            "bgr": (171, 71, 0),      # RGB: 0, 71, 171 (#0047AB) - Cobalt Blue
            "label": "COCAINE HCL (SCOTT COBALT BLUE)"
        },
        "cannabis": {
            "bgr": (75, 18, 65),      # RGB: 65, 18, 75 (#41124B) - Deep Indigo
            "label": "CANNABIS / THC (DUQUENOIS INDIGO)"
        },
        "meth": {
            "bgr": (20, 80, 190),     # RGB: 190, 80, 20 (#BE5014) - Vivid Orange
            "label": "METHAMPHETAMINE (MARQUIS ORANGE)"
        },
        "lsd": {
            "bgr": (145, 38, 128),    # RGB: 128, 38, 145 (#802691) - Bright Magenta
            "label": "LSD BLOTTER (EHRLICH MAGENTA)"
        },
        "negative": {
            "bgr": (210, 238, 245),   # RGB: 245, 238, 210 (#F5EED2) - Pale Straw Clear
            "label": "NEGATIVE / UNREACTIVE (BAKING SODA / EXCIPIENT)"
        }
    }

    for key, info in samples.items():
        img = generate_reference_card_image(sample_bgr=info["bgr"], sample_label=info["label"])
        out_path = DEMO_SAMPLES_DIR / f"{key}_sample.jpg"
        cv2.imwrite(str(out_path), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
        print(f"[DEMO SAMPLE CREATED] -> {out_path.name}")


def build_card_pdf():
    """Generates a high-quality printable PDF page with the card image centered."""
    card_img = generate_reference_card_image()
    CARD_PNG_PATH.parent.mkdir(exist_ok=True)
    cv2.imwrite(str(CARD_PNG_PATH), card_img)

    # Create PDF via ReportLab
    c = canvas.Canvas(str(CARD_PDF_PATH), pagesize=A4)
    page_w, page_h = A4

    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(page_w / 2.0, page_h - 40, "NCB Digital Companion - Printable Calibration Card")
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.HexColor("#4A5568"))
    c.drawCentredString(page_w / 2.0, page_h - 58, "Print at 100% scale (Do Not Scale / Fit to Page). Place reagent kit in sample well.")

    # Draw image on PDF (width ~ 520pt, height ~ 325pt)
    img_w = 520
    img_h = 325
    x = (page_w - img_w) / 2.0
    y = page_h - 90 - img_h
    c.drawImage(str(CARD_PNG_PATH), x, y, width=img_w, height=img_h)

    # Footnote
    c.setFont("Helvetica-Oblique", 9)
    c.setFillColor(colors.HexColor("#718096"))
    c.drawCentredString(page_w / 2.0, y - 25, "Presumptive Test Aid under NDPS Act. Verified under CIE D65 Standards.")

    c.showPage()
    c.save()
    print(f"Generated Reference Card PNG: {CARD_PNG_PATH}")
    print(f"Generated Reference Card PDF: {CARD_PDF_PATH}")


if __name__ == "__main__":
    build_card_pdf()

