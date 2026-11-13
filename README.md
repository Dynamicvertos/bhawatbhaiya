# Digital Companion for Field Drug Testing
**Problem Statement ID:** 26231  
**Organization:** Ministry of Home Affairs | Narcotics Control Bureau (NCB)  
**Theme:** MedTech / BioTech / HealthTech | Digital Forensics  
**Deliverable:** Working Mobile/Web Application Prototype (Colorimetric Calibration & Chain-of-Custody)

---

## 1. Executive Summary & Problem Solved

Field drug-testing kits (e.g., Marquis, Scott, Duquenois-Levine) rely on chemical color-change reactions. In real field operations, these tests suffer from two critical flaws:
1. **Subjective Interpretation & Ambient Lighting Bias:** Sunlight, fluorescent office lights, or sodium streetlights radically alter RGB pixel values, leading to misclassification by human eyes or uncalibrated camera sensors.
2. **No Evidentiary Verifiability:** Field test outcomes cannot currently be relied upon as documentary evidence in court under the NDPS Act because there is no cryptographic proof that the test was conducted at a specific place and time without tampering.

### The Solution:
This project delivers a **full-stack mobile companion** that requires **no new hardware**:
- **Computer Vision Color Calibration Engine:** Uses an in-frame reference card with 4-corner ArUco fiducials to rectify perspective and apply **Von Kries / CIELAB Chromatic Adaptation** against standardized reference swatches (D65 White, 18% Neutral Gray).
- **Explainable Colorimetric Matching ($\Delta E_{00}$):** Calculates scientific color distance in CIE $L^*a^*b^*$ color space against official NIJ / UNODC reagent palettes (Marquis, Scott, Duquenois, Ehrlich, Mecke) instead of relying on an unexplainable black-box neural net.
- **Tamper-Evident Chain-of-Custody:** Immediately computes a **SHA-256 cryptographic digest** of the raw captured image, anchors it with GPS coordinates, ISO UTC timestamps, and operator badge IDs, generating an HMAC digital signature.
- **Official Evidentiary Certificate (PDF + QR):** Automatically generates a court-ready PDF test certificate embedded with a scannable QR verification link.
- **Searchable Field Seizure Registry:** Maintains an indexed audit log stored in **Supabase PostgreSQL** (with automatic zero-crash fallback to local SQLite).

---

## 2. System Architecture

```
                                 [ Field Officer Phone ]
                                            │
                             (Camera Capture / File Upload)
                                            │
                                            ▼
                    ┌────────────────────────────────────────────────┐
                    │            FastAPI Backend Engine              │
                    └───────────────────────┬────────────────────────┘
                                            │
                   ┌────────────────────────┴────────────────────────┐
                   ▼                                                 ▼
     [ Computer Vision Engine ]                        [ Digital Forensics Engine ]
  - 4-Corner ArUco Detection                        - Raw Frame SHA-256 Hashing
  - Homography Rectification                        - GPS & UTC Timestamp Anchoring
  - White & 18% Gray Sampling                       - Operator Badge HMAC Signing
  - Lighting Gain Normalization                     - ReportLab PDF Certificate Gen
  - CIE L*a*b* Delta-E Matcher                      - Scannable Verification QR Code
                   │                                                 │
                   └────────────────────────┬────────────────────────┘
                                            ▼
                               [ Unified Persistence ]
                           ┌─────────────────────────┐
                           │   Supabase PostgreSQL   │ (Cloud Primary)
                           │   & Object Storage      │
                           ├─────────────────────────┤
                           │   Local SQLite & Disk   │ (Offline Fallback)
                           └─────────────────────────┘
```

---

## 3. Supported Chemical Reagent Kits

| Reagent Kit | Primary Target Substances | Expected Positive Reaction | Standard Metric |
| :--- | :--- | :--- | :--- |
| **Marquis Reagent** | Heroin / Morphine, Amphetamines, MDMA | Dark Violet/Purple (Opiates), Orange (Amphetamine), Black (MDMA) | $\Delta E \le 25.0$ |
| **Scott Reagent** | Cocaine HCl & Freebase | Cobalt Blue Precipitate in HCl phase | $\Delta E \le 28.0$ |
| **Duquenois-Levine** | Cannabis / THC / Hashish | Indigo / Deep Violet extracted into lower layer | $\Delta E \le 25.0$ |
| **Ehrlich's Reagent** | LSD & Indole Alkaloids | Intense Purple / Magenta reaction | $\Delta E \le 26.0$ |
| **Mecke Reagent** | Heroin vs. Oxycodone | Forest Green to Deep Blue-Green | $\Delta E \le 25.0$ |

---

## 4. Quick Start (Run Locally in 10 Seconds)

### Step 1: Install Requirements
```powershell
python -m pip install -r requirements.txt
```

### Step 2: Seed Sample Data
Populates the audit log with 3 realistic field test records:
```powershell
python seed_sample_data.py
```

### Step 3: Start the Application Server
```powershell
python run_server.py
```
Open **`http://localhost:8000`** on your browser, or visit **`http://<your-lan-ip>:8000`** on your mobile phone connected to the same Wi-Fi.

---

## 5. Connecting Supabase (Optional - 3 Minutes)

The app already works 100% out-of-the-box using the built-in SQLite engine. To enable live Supabase Cloud synchronization:

1. Create a free project at [supabase.com](https://supabase.com).
2. Open the **SQL Editor** in Supabase and paste the contents of `supabase_schema.sql`. Click **Run**.
3. Under **Storage**, create two public buckets:
   - `drug-test-images`
   - `drug-test-certificates`
4. Copy `.env.example` to `.env`:
   ```ini
   SUPABASE_URL=https://your-project-id.supabase.co
   SUPABASE_KEY=your-supabase-anon-or-service-role-key
   ```
5. Restart `python run_server.py`. The top banner badge will automatically switch to **"Cloud DB"**!

---

## 6. How to Test the Computer Vision Color Calibration

1. Run `python generate_reference_card.py` (already generated in `data/reference_card.pdf` and `data/reference_card.png`).
2. Print `reference_card.pdf` or display `reference_card.png` on an iPad, tablet, or another phone screen.
3. Open the app on your phone, choose **Marquis Reagent**, and snap a photo containing the card.
4. The system detects the 4 ArUco markers, rectifies the perspective, performs lighting calibration, and issues the official result certificate!

---

## 7. 100% Free Cloud Deployment

### Deploying to Render.com (Free Tier):
1. Push this folder to a GitHub repository.
2. In Render Dashboard, click **New +** $\rightarrow$ **Web Service**.
3. Select your GitHub repository.
4. Set:
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Under **Environment Variables**, add:
   - `SUPABASE_URL` = your Supabase URL
   - `SUPABASE_KEY` = your Supabase key
   - `BASE_URL` = `https://your-app-name.onrender.com`
6. Click **Deploy**. Render gives you a free HTTPS link ready for your mobile camera demo!

---

## 8. College Capstone & Viva Q&A Cheat Sheet

**Q1: Why didn't you just train a Convolutional Neural Network (CNN) on photos?**  
*Answer:* Ambient lighting (sunlight vs yellow streetlights) shifts camera RGB pixel values by 30-60%. An uncalibrated CNN will give false positives in low light. Furthermore, court evidence under the NDPS Act demands **explainable science** ($\Delta E_{00}$ colorimetric distance against chemical standards), not an unexplainable black-box prediction.

**Q2: What is the purpose of the reference card?**  
*Answer:* It provides standard D65 White and 18% Neutral Gray patches alongside 4 ArUco fiducials. When the phone takes a photo at an angle, homography rectifies the card to a flat plane, and the white/gray swatches calculate channel-wise lighting gains to remove color temperature distortion.

**Q3: How does this guarantee evidence integrity?**  
*Answer:* The raw image bytes are hashed using **SHA-256** before any processing. The hash is cryptographically bound to the GPS coordinates, UTC timestamp, and officer ID via HMAC. Any modification to the image or record immediately invalidates the signature.

**Q4: Does this replace lab tests?**  
*Answer:* No. Under statutory guidelines, this is a **presumptive field screening record** to establish probable cause and maintain chain-of-custody. Final confirmation is conducted in a forensic laboratory via GC-MS or HPLC.

