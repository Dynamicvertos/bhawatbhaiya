# -*- coding: utf-8 -*-
"""
Build NCB-SPECTRA.apk
1. Downloads / loads template WebView APK from mikespub-archive/android-webview v1.28
2. Replaces assets/settings.json to point to https://bhawatbhaiya.onrender.com (and local fallbacks)
3. Strips old signatures and performs 4-byte zipalign
4. Re-signs using uber-apk-signer with APK Signature Scheme v1, v2, and v3
5. Outputs ready-to-install, universally compatible NCB-SPECTRA.apk!
"""

import os
import json
import zipfile
import io
import urllib.request
import subprocess
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).parent
OUTPUT_APK = BASE_DIR / "NCB-SPECTRA.apk"
KEYSTORE = BASE_DIR / "ncb.keystore"
TOOLS_DIR = BASE_DIR / "tools"
UBER_SIGNER = TOOLS_DIR / "uber-apk-signer.jar"
CACHED_TEMPLATE = TOOLS_DIR / "template-app-release.apk"

JDK_BIN = Path(r"C:\Program Files\Eclipse Adoptium\jdk-21.0.9.10-hotspot\bin")
JAVA_EXE = JDK_BIN / "java.exe" if (JDK_BIN / "java.exe").exists() else Path("java")

TEMPLATE_URL = "https://github.com/mikespub-archive/android-webview/releases/download/v1.28/app-release.apk"

# Step 1: Obtain template APK
print("Step 1: Obtaining WebView base APK template...")
TOOLS_DIR.mkdir(exist_ok=True)

if CACHED_TEMPLATE.exists() and CACHED_TEMPLATE.stat().st_size > 1000000:
    print(f"Using cached base template ({CACHED_TEMPLATE.stat().st_size:,} bytes)...")
    with open(CACHED_TEMPLATE, "rb") as f:
        raw_apk = f.read()
elif OUTPUT_APK.exists() and OUTPUT_APK.stat().st_size > 1000000:
    print(f"Using existing base APK ({OUTPUT_APK.stat().st_size:,} bytes)...")
    with open(OUTPUT_APK, "rb") as f:
        raw_apk = f.read()
    with open(CACHED_TEMPLATE, "wb") as f:
        f.write(raw_apk)
else:
    print(f"Downloading WebView APK template from {TEMPLATE_URL}...")
    req = urllib.request.Request(TEMPLATE_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        raw_apk = resp.read()
    with open(CACHED_TEMPLATE, "wb") as f:
        f.write(raw_apk)
    print(f"Downloaded and cached {len(raw_apk):,} bytes.")

# Step 2: Inject Cloud Settings and Direct Auto-Redirect into APK Assets
print("\nStep 2: Customizing APK for direct launch into https://bhawatbhaiya.onrender.com...")
in_zip = zipfile.ZipFile(io.BytesIO(raw_apk))
temp_apk_path = BASE_DIR / "temp_unsigned.apk"

# Splash screen with instant redirect and dark tactical UI styling (no plain white menu/options)
SPLASH_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
  <title>NCB-SPECTRA Field Drug Forensics</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    html, body {
      width: 100%;
      height: 100%;
      background-color: #080D1A;
      color: #F8FAFC;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      overflow: hidden;
    }
    .scanner-box {
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
      padding: 24px;
    }
    .pulse-ring {
      width: 58px;
      height: 58px;
      border: 4px solid rgba(245, 158, 11, 0.18);
      border-top-color: #F59E0B;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
      margin-bottom: 22px;
      box-shadow: 0 0 24px rgba(245, 158, 11, 0.4);
    }
    @keyframes spin {
      to { transform: rotate(360deg); }
    }
    .badge {
      display: inline-block;
      font-family: monospace;
      font-size: 10px;
      font-weight: 800;
      color: #10B981;
      background: rgba(16, 185, 129, 0.12);
      border: 1px solid rgba(16, 185, 129, 0.3);
      padding: 4px 10px;
      border-radius: 6px;
      letter-spacing: 0.08em;
      margin-bottom: 12px;
      text-transform: uppercase;
    }
    .title {
      font-family: monospace;
      font-size: 16px;
      font-weight: 900;
      letter-spacing: 0.14em;
      color: #F59E0B;
      text-transform: uppercase;
      margin-bottom: 6px;
    }
    .sub {
      font-family: monospace;
      font-size: 11px;
      color: #94A3B8;
      letter-spacing: 0.05em;
    }
  </style>
  <script>
    // Immediately and unconditionally launch into the live Bhagwat Bhaiya application
    window.location.replace("https://bhawatbhaiya.onrender.com");
  </script>
</head>
<body>
  <div class="scanner-box">
    <div class="badge">SECURE FORENSIC PROTOCOL</div>
    <div class="pulse-ring"></div>
    <div class="title">NCB-SPECTRA</div>
    <div class="sub">INITIALIZING SECURE CHAMBER...</div>
  </div>
</body>
</html>
"""

new_settings = {
    "sites": [
        {
            "url": "https://bhawatbhaiya.onrender.com",
            "title": "NCB-SPECTRA"
        }
    ],
    "other": "https://bhawatbhaiya.onrender.com",
    "match": [
        ["host", "equals", "bhawatbhaiya.onrender.com"],
        ["host", "endsWith", ".onrender.com"],
        ["host", "equals", "10.87.216.184"],
        ["host", "equals", "localhost"],
        ["host", "equals", "127.0.0.1"]
    ],
    "skip": [
        ["path", "endsWith", ".epub"]
    ],
    "remote_debug": True,
    "console_log": True,
    "js_interface": True,
    "context_menu": False,
    "not_matching": False,
    "local_sites": False,
    "update_zip": "",
    "web_settings": {
        "JavaScriptEnabled": True,
        "DomStorageEnabled": True,
        "AllowFileAccess": True,
        "MediaPlaybackRequiresUserGesture": False
    },
    "source": "remote",
    "timestamp": "2026-11-13T11:28:00Z"
}

with zipfile.ZipFile(temp_apk_path, "w", zipfile.ZIP_DEFLATED) as out_zip:
    for item in in_zip.infolist():
        # Exclude old signatures
        if item.filename.startswith("META-INF/"):
            continue
        # Replace configuration
        if item.filename == "assets/settings.json":
            out_zip.writestr(item, json.dumps(new_settings, indent=2))
        # Replace internal HTML entrypoints with instant direct redirect
        elif item.filename in [
            "assets/web/index.html",
            "assets/local/index.html",
            "assets/local/sites.html",
            "assets/demo/index.html",
            "assets/demo/test.html"
        ]:
            out_zip.writestr(item, SPLASH_HTML)
        else:
            out_zip.writestr(item, in_zip.read(item.filename))

print("✓ Replaced all template selection/menu forms with direct auto-redirect to https://bhawatbhaiya.onrender.com!")

# Copy unsigned APK to target path
if OUTPUT_APK.exists():
    OUTPUT_APK.unlink()
shutil.copyfile(temp_apk_path, OUTPUT_APK)
temp_apk_path.unlink()

# Step 3: Sign & Zipalign with uber-apk-signer (v1, v2, v3 schemes)
print("\nStep 3: Zipaligning & Signing with uber-apk-signer (Scheme v1 + v2 + v3)...")

if not UBER_SIGNER.exists():
    raise FileNotFoundError(f"uber-apk-signer not found at {UBER_SIGNER}")

sign_cmd = [
    str(JAVA_EXE),
    "-jar", str(UBER_SIGNER),
    "--apks", str(OUTPUT_APK),
    "--overwrite",
    "--allowResign",
    "--verbose"
]

res = subprocess.run(sign_cmd, capture_output=True, text=True)
print(res.stdout)
if res.returncode != 0:
    print("Signer Error:", res.stderr)
    raise RuntimeError("Signing failed!")

# Step 4: Verification
print("\nStep 4: Verifying Final APK Signatures...")
verify_cmd = [
    str(JAVA_EXE),
    "-jar", str(UBER_SIGNER),
    "--apks", str(OUTPUT_APK),
    "--onlyVerify",
    "--verbose"
]
res_ver = subprocess.run(verify_cmd, capture_output=True, text=True)
print(res_ver.stdout)

print("\n" + "=" * 60)
print(f"SUCCESS: Universal Android APK created at:")
print(f"  {OUTPUT_APK}")
print(f"Size: {OUTPUT_APK.stat().st_size:,} bytes")
print(f"Embedded Cloud Endpoint: https://bhawatbhaiya.onrender.com")
print("=" * 60)
