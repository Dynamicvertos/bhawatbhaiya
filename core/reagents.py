"""
Reagent Chemical Standards and Colorimetry Matcher for NCB Field Drug Tests.
Based on standard forensic reagent chemistry (UNODC / NIJ Reagent Standards).
"""

import math
from typing import Dict, Any, List, Tuple

# Standard Reagent database with chemical profiles and calibrated standard sRGB colors
REAGENT_STANDARDS: Dict[str, Dict[str, Any]] = {
    "marquis": {
        "id": "marquis",
        "name": "Marquis Reagent",
        "target_class": "Opiates, Amphetamines & MDMA",
        "description": "Formaldehyde & concentrated sulfuric acid solution. Primary field screen under NDPS.",
        "outcomes": [
            {
                "substance": "Heroin / Morphine (Opiates)",
                "category": "POSITIVE",
                "rgb": [59, 10, 69],        # Deep reddish violet / purple
                "hex": "#3B0A45",
                "min_delta_e": 25.0,
                "notes": "Fast transition from reddish to intense dark purple."
            },
            {
                "substance": "Amphetamine / Methamphetamine",
                "category": "POSITIVE",
                "rgb": [190, 80, 20],        # Vivid Orange to Red-Orange
                "hex": "#BE5014",
                "min_delta_e": 24.0,
                "notes": "Rapid shift to bright orange, darkening to reddish-brown."
            },
            {
                "substance": "MDMA (Ecstasy)",
                "category": "POSITIVE",
                "rgb": [20, 10, 35],         # Dark Purple to Jet Black
                "hex": "#140A23",
                "min_delta_e": 22.0,
                "notes": "Instant blackening with deep purple hue."
            },
            {
                "substance": "Unreactive / Negative (No Controlled Drug)",
                "category": "NEGATIVE",
                "rgb": [245, 238, 210],      # Pale straw / unreacted clear
                "hex": "#F5EED2",
                "min_delta_e": 28.0,
                "notes": "No characteristic chromogenic reaction."
            }
        ]
    },
    "scott": {
        "id": "scott",
        "name": "Scott Reagent (Ruybal)",
        "target_class": "Cocaine Hydrochloride & Base",
        "description": "Cobalt thiocyanate solution. 3-step field test for presumptive cocaine identification.",
        "outcomes": [
            {
                "substance": "Cocaine Presumptive (HCl / Base)",
                "category": "POSITIVE",
                "rgb": [0, 71, 171],         # Cobalt / Royal Blue precipitate
                "hex": "#0047AB",
                "min_delta_e": 28.0,
                "notes": "Formation of cobalt blue precipitate in hydrochloric acid phase."
            },
            {
                "substance": "Unreactive / Negative (Non-Cocaine)",
                "category": "NEGATIVE",
                "rgb": [245, 210, 205],      # Pink / salmon unreactive background
                "hex": "#F5D2CD",
                "min_delta_e": 26.0,
                "notes": "Reagent remains pink or turns clear without blue layer."
            }
        ]
    },
    "duquenois_levine": {
        "id": "duquenois_levine",
        "name": "Duquenois-Levine Reagent",
        "target_class": "Cannabis / THC / Hashish",
        "description": "Vanillin & acetaldehyde in ethanol. Standard test for tetrahydrocannabinols.",
        "outcomes": [
            {
                "substance": "Cannabis / THC Presumptive",
                "category": "POSITIVE",
                "rgb": [65, 18, 75],         # Deep Indigo / Violet in lower layer
                "hex": "#41124B",
                "min_delta_e": 25.0,
                "notes": "Extraction of deep indigo/violet pigment into the lower chloroform layer."
            },
            {
                "substance": "Unreactive / Negative",
                "category": "NEGATIVE",
                "rgb": [220, 215, 195],      # Murky greenish-yellow / unextracted
                "hex": "#DCD7C3",
                "min_delta_e": 28.0,
                "notes": "No violet pigment extracted into bottom organic solvent."
            }
        ]
    },
    "ehrlich": {
        "id": "ehrlich",
        "name": "Ehrlich's Reagent",
        "target_class": "LSD & Indole Alkaloids",
        "description": "p-DMAB in concentrated acid. Presumptive field test for lysergamides and psilocybin.",
        "outcomes": [
            {
                "substance": "LSD / Indole Alkaloid Presumptive",
                "category": "POSITIVE",
                "rgb": [128, 38, 145],       # Bright purple / violet
                "hex": "#802691",
                "min_delta_e": 26.0,
                "notes": "Characteristic intense purple/magenta reaction within 1-3 minutes."
            },
            {
                "substance": "Unreactive / Negative",
                "category": "NEGATIVE",
                "rgb": [250, 248, 235],      # Pale clear
                "hex": "#FAF8EB",
                "min_delta_e": 28.0,
                "notes": "Reagent remains colorless or pale straw yellow."
            }
        ]
    },
    "mecke": {
        "id": "mecke",
        "name": "Mecke Reagent",
        "target_class": "Heroin vs Oxycodone",
        "description": "Selenious acid in concentrated sulfuric acid. Differentiates opiate derivatives.",
        "outcomes": [
            {
                "substance": "Heroin Presumptive",
                "category": "POSITIVE",
                "rgb": [11, 102, 35],        # Forest / Deep Green to Blue-Green
                "hex": "#0B6623",
                "min_delta_e": 25.0,
                "notes": "Immediate transition from green to deep blue-green."
            },
            {
                "substance": "Unreactive / Negative",
                "category": "NEGATIVE",
                "rgb": [245, 240, 220],
                "hex": "#F5F0DC",
                "min_delta_e": 27.0,
                "notes": "No green chromatic change observed."
            }
        ]
    }
}


def rgb_to_cielab(rgb: Tuple[int, int, int]) -> Tuple[float, float, float]:
    """
    Converts sRGB [0-255] to CIE L*a*b* standard D65 illuminant.
    Scientifically sound color space transformation.
    """
    # 1. Normalize and sRGB gamma expansion
    r, g, b = [x / 255.0 for x in rgb]
    r = ((r + 0.055) / 1.055) ** 2.4 if r > 0.04045 else r / 12.92
    g = ((g + 0.055) / 1.055) ** 2.4 if g > 0.04045 else g / 12.92
    b = ((b + 0.055) / 1.055) ** 2.4 if b > 0.04045 else b / 12.92

    # 2. Convert to CIE XYZ (Observer = 2°, Illuminant = D65)
    X = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
    Y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    Z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041

    # D65 Reference White
    Xn, Yn, Zn = 0.95047, 1.00000, 1.08883
    xr, yr, zr = X / Xn, Y / Yn, Z / Zn

    def f(t: float) -> float:
        return t ** (1.0 / 3.0) if t > 0.008856 else (7.787 * t) + (16.0 / 116.0)

    L = (116.0 * f(yr)) - 16.0
    a = 500.0 * (f(xr) - f(yr))
    b = 200.0 * (f(yr) - f(zr))

    return L, a, b


def calculate_delta_e(lab1: Tuple[float, float, float], lab2: Tuple[float, float, float]) -> float:
    """
    Computes standard CIE Delta E (CIE76 / Euclidean in CIELAB space).
    Delta E < 5.0 is barely distinguishable to human eye; Delta E < 25.0 matches forensic class.
    """
    dL = lab1[0] - lab2[0]
    da = lab1[1] - lab2[1]
    db = lab1[2] - lab2[2]
    return math.sqrt(dL * dL + da * da + db * db)


def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(int(rgb[0]), int(rgb[1]), int(rgb[2])).upper()


def match_color_against_reagent(
    observed_rgb: Tuple[int, int, int],
    reagent_id: str
) -> Dict[str, Any]:
    """
    Matches an observed calibrated RGB sample against the specified reagent standard.
    Returns: classification, confidence score, Delta E metric, and scientific explanation.
    """
    reagent = REAGENT_STANDARDS.get(reagent_id.lower())
    if not reagent:
        raise ValueError(f"Unknown reagent identifier '{reagent_id}'.")

    obs_lab = rgb_to_cielab(observed_rgb)
    outcomes = reagent["outcomes"]

    best_match = None
    min_dist = float("inf")

    scored_outcomes = []
    for outcome in outcomes:
        target_rgb = tuple(outcome["rgb"])
        target_lab = rgb_to_cielab(target_rgb)
        dist = calculate_delta_e(obs_lab, target_lab)
        
        # Max allowable tolerance for a conclusive match
        threshold = outcome.get("min_delta_e", 25.0)
        
        # Compute confidence score: 100% when dE = 0, decaying towards threshold
        confidence = max(0.0, min(99.4, (1.0 - (dist / (threshold * 1.5))) * 100.0))
        
        scored_outcomes.append({
            "outcome": outcome,
            "delta_e": round(dist, 2),
            "confidence": round(confidence, 1),
            "threshold": threshold
        })

        if dist < min_dist:
            min_dist = dist
            best_match = scored_outcomes[-1]

    # Evaluate classification
    if best_match and best_match["delta_e"] <= best_match["threshold"]:
        chosen_outcome = best_match["outcome"]
        result_category = chosen_outcome["category"]
        substance = chosen_outcome["substance"]
        confidence = best_match["confidence"]
        explanation = (
            f"Observed reaction color matches calibrated standard for {substance}. "
            f"CIE Delta E is {best_match['delta_e']} (within threshold ≤ {best_match['threshold']}). "
            f"{chosen_outcome['notes']}"
        )
    else:
        # Distance too high to be definitive
        result_category = "INCONCLUSIVE"
        substance = "Unrecognized Chromogenic Reaction"
        confidence = round(max(30.0, 100.0 - min_dist), 1) if min_dist < 100 else 25.0
        explanation = (
            f"The observed reaction color (Delta E: {round(min_dist, 2)}) did not definitively "
            f"match standard positive or negative baseline profiles for {reagent['name']}. "
            f"Field recommendation: Repeat test with fresh kit or forward to laboratory for GC-MS confirmatory testing."
        )

    return {
        "reagent_id": reagent["id"],
        "reagent_name": reagent["name"],
        "target_class": reagent["target_class"],
        "result_category": result_category,
        "detected_substance": substance,
        "confidence_score": confidence,
        "delta_e_metric": round(min_dist, 2),
        "explanation": explanation,
        "observed_hex": rgb_to_hex(observed_rgb),
        "expected_hex": best_match["outcome"]["hex"] if best_match else "#FFFFFF",
        "detailed_matches": scored_outcomes
    }

