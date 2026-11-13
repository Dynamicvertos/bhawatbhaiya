"""
Computer Vision Color Calibration Engine for NCB Field Drug Testing.
Handles ArUco fiducial detection, perspective rectification,
and chromatic adaptation (lighting normalization) using reference swatches.
"""

import cv2
import numpy as np
from typing import Tuple, Dict, Any, Optional

# Reference Card Swatch Calibration Targets (sRGB)
CALIBRATION_TARGET_WHITE = np.array([245.0, 245.0, 245.0], dtype=np.float32)
CALIBRATION_TARGET_GRAY  = np.array([118.0, 118.0, 118.0], dtype=np.float32)
CALIBRATION_TARGET_BLACK = np.array([30.0, 30.0, 30.0], dtype=np.float32)


def get_aruco_detector():
    """Initializes OpenCV ArUco detector across OpenCV 4.x versions."""
    try:
        # OpenCV 4.7+ API
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        parameters = cv2.aruco.DetectorParameters()
        detector = cv2.aruco.ArucoDetector(dictionary, parameters)
        return detector, "NEW_API"
    except AttributeError:
        # Legacy OpenCV 4.x API
        dictionary = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50)
        parameters = cv2.aruco.DetectorParameters_create()
        return (dictionary, parameters), "LEGACY_API"


def detect_aruco_corners(image_bgr: np.ndarray):
    """Detects ArUco markers in the given image."""
    detector, api_type = get_aruco_detector()
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    
    if api_type == "NEW_API":
        corners, ids, rejected = detector.detectMarkers(gray)
    else:
        dictionary, parameters = detector
        corners, ids, rejected = cv2.aruco.detectMarkers(gray, dictionary, parameters=parameters)
        
    return corners, ids


def rectify_reference_card(
    image_bgr: np.ndarray,
    card_width: int = 800,
    card_height: int = 500
) -> Tuple[Optional[np.ndarray], bool]:
    """
    Attempts to locate the 4 corner ArUco markers (IDs 0: Top-Left, 1: Top-Right,
    2: Bottom-Right, 3: Bottom-Left) and warp the card into a flat rectangle.
    """
    corners, ids = detect_aruco_corners(image_bgr)
    
    if ids is None or len(ids) < 4:
        return None, False
    
    id_map = {int(i[0]): c[0] for i, c in zip(ids, corners)}
    
    # Check if all 4 corner markers (0, 1, 2, 3) are visible
    if not all(k in id_map for k in [0, 1, 2, 3]):
        return None, False

    # Extract center point of each marker
    pts_src = np.array([
        np.mean(id_map[0], axis=0),  # Top-Left (ID 0)
        np.mean(id_map[1], axis=0),  # Top-Right (ID 1)
        np.mean(id_map[2], axis=0),  # Bottom-Right (ID 2)
        np.mean(id_map[3], axis=0)   # Bottom-Left (ID 3)
    ], dtype=np.float32)

    # Destination rectangular plane
    margin = 40
    pts_dst = np.array([
        [margin, margin],
        [card_width - margin, margin],
        [card_width - margin, card_height - margin],
        [margin, card_height - margin]
    ], dtype=np.float32)

    # Perspective homography transformation
    matrix = cv2.getPerspectiveTransform(pts_src, pts_dst)
    warped = cv2.warpPerspective(image_bgr, matrix, (card_width, card_height))
    return warped, True


def extract_card_calibration_gains(warped_card_bgr: np.ndarray) -> np.ndarray:
    """
    Samples the White and 18% Neutral Gray patches on the rectified card
    to calculate the channel-wise lighting compensation gains (Von Kries scaling).
    """
    h, w, _ = warped_card_bgr.shape
    
    # Coordinates of reference swatches on standardized card:
    # White swatch: centered at (w * 0.22, h * 0.35)
    # Gray swatch:  centered at (w * 0.22, h * 0.65)
    wh_x, wh_y = int(w * 0.22), int(h * 0.35)
    gr_x, gr_y = int(w * 0.22), int(h * 0.65)
    radius = int(min(w, h) * 0.04)

    # Extract mean colors in RGB
    white_patch = warped_card_bgr[wh_y-radius:wh_y+radius, wh_x-radius:wh_x+radius]
    gray_patch  = warped_card_bgr[gr_y-radius:gr_y+radius, gr_x-radius:gr_x+radius]

    if white_patch.size == 0 or gray_patch.size == 0:
        return np.array([1.0, 1.0, 1.0], dtype=np.float32)

    obs_white_bgr = np.mean(white_patch, axis=(0, 1))
    obs_white_rgb = np.array([obs_white_bgr[2], obs_white_bgr[1], obs_white_bgr[0]], dtype=np.float32)
    obs_white_rgb = np.maximum(obs_white_rgb, 1.0) # Avoid divide by zero

    # Compute gain to shift observed white to calibrated target D65 white
    gains_rgb = CALIBRATION_TARGET_WHITE / obs_white_rgb
    
    # Clip gains to sane ranges [0.4, 2.5] to prevent runaway noise
    gains_rgb = np.clip(gains_rgb, 0.4, 2.5)
    return gains_rgb


def extract_sample_well_color(warped_card_bgr: np.ndarray, gains_rgb: np.ndarray) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
    """
    Extracts the reaction sample from the designated Reaction Well zone on the card.
    Returns: (raw_rgb, calibrated_rgb).
    """
    h, w, _ = warped_card_bgr.shape
    # Reaction Well is placed at center-right of the card: (w * 0.65, h * 0.50)
    cx, cy = int(w * 0.65), int(h * 0.50)
    r = int(min(w, h) * 0.12)

    sample_roi = warped_card_bgr[cy-r:cy+r, cx-r:cx+r]
    mean_bgr = np.mean(sample_roi, axis=(0, 1))
    raw_rgb = np.array([mean_bgr[2], mean_bgr[1], mean_bgr[0]], dtype=np.float32)

    # Apply lighting correction gains
    calibrated_rgb = raw_rgb * gains_rgb
    calibrated_rgb = np.clip(calibrated_rgb, 0.0, 255.0)

    raw_tuple = (int(raw_rgb[0]), int(raw_rgb[1]), int(raw_rgb[2]))
    cal_tuple = (int(calibrated_rgb[0]), int(calibrated_rgb[1]), int(calibrated_rgb[2]))
    return raw_tuple, cal_tuple


def auto_white_balance_fallback(image_bgr: np.ndarray) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
    """
    Fallback method when no reference card is detected in frame.
    Uses Gray World White Balance assumption over the central Region-Of-Interest.
    """
    h, w, _ = image_bgr.shape
    # Central 30% crop
    cy, cx = h // 2, w // 2
    ry, rx = int(h * 0.15), int(w * 0.15)
    roi = image_bgr[cy-ry:cy+ry, cx-rx:cx+rx]

    mean_bgr = np.mean(roi, axis=(0, 1))
    raw_rgb = (int(mean_bgr[2]), int(mean_bgr[1]), int(mean_bgr[0]))

    # Gray World assumption: average RGB of image should be gray
    img_mean_bgr = np.mean(image_bgr, axis=(0, 1))
    gray_val = (img_mean_bgr[0] + img_mean_bgr[1] + img_mean_bgr[2]) / 3.0
    
    gains_bgr = gray_val / np.maximum(img_mean_bgr, 1.0)
    cal_bgr = mean_bgr * gains_bgr
    cal_bgr = np.clip(cal_bgr, 0.0, 255.0)
    
    cal_rgb = (int(cal_bgr[2]), int(cal_bgr[1]), int(cal_bgr[0]))
    return raw_rgb, cal_rgb


def process_image_for_colorimetry(image_bytes: bytes) -> Dict[str, Any]:
    """
    Main entry point for CV processing.
    Accepts raw image bytes, attempts card rectification and lighting calibration.
    Returns calibrated RGB, raw RGB, and calibration status metadata.
    """
    np_arr = np.frombuffer(image_bytes, np.uint8)
    image_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if image_bgr is None:
        raise ValueError("Invalid image format or corrupted file.")

    # 1. Attempt ArUco Reference Card Detection
    warped_card, card_detected = rectify_reference_card(image_bgr)

    if card_detected and warped_card is not None:
        gains_rgb = extract_card_calibration_gains(warped_card)
        raw_rgb, cal_rgb = extract_sample_well_color(warped_card, gains_rgb)
        method = "ARUCO_REFERENCE_CARD"
        status_note = "Lighting calibrated via 4-corner ArUco fiducials and reference swatches."
    else:
        # Fallback to central ROI + Gray World
        raw_rgb, cal_rgb = auto_white_balance_fallback(image_bgr)
        method = "AUTO_WHITE_BALANCE"
        status_note = "Reference card not detected in frame. Applied automatic gray-world lighting normalization."

    return {
        "card_detected": card_detected,
        "calibration_method": method,
        "status_note": status_note,
        "raw_rgb": raw_rgb,
        "calibrated_rgb": cal_rgb,
        "image_width": image_bgr.shape[1],
        "image_height": image_bgr.shape[0]
    }

