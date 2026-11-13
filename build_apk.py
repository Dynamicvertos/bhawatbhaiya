# -*- coding: utf-8 -*-
"""
Build NCB-SPECTRA.apk
1. Downloads template WebView APK from mikespub-archive/android-webview v1.28
2. Replaces assets/settings.json to point to http://10.87.216.184:8000 and http://localhost:8000
3. Strips old signature
4. Re-signs with a 2048-bit RSA keystore using JDK 21 jarsigner
5. Outputs final ready-to-install NCB-SPECTRA.apk!
"""

import os
import json
import zipfile
import urllib.request
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).parent
OUTPUT_APK = BASE_DIR / "NCB-SPECTRA.apk"
KEYSTORE = BASE_DIR / "ncb.keystore"
JDK_BIN = Path(r"C:\Program Files\Eclipse Adoptium\jdk-21.0.9.10-hotspot\bin")
KEYTOOL = JDK_BIN / "keytool.exe"
JARSIGNER = JDK_BIN / "jarsigner.exe"

TEMPLATE_URL = "https://github.com/mikespub-archive/android-webview/releases/download/v1.28/app-release.apk"

print("Step 1: Downloading WebView APK base template...")
req = urllib.request.Request(TEMPLATE_URL, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req) as resp:
    raw_apk = resp.read()
print(f"Downloaded {len(raw_apk)} bytes.")

print("Step 2: Customizing APK assets for NCB-SPECTRA...")
in_zip = zipfile.ZipFile(io.BytesIO(raw_apk)) if 'io' in locals() else None

import io
in_zip = zipfile.ZipFile(io.BytesIO(raw_apk))
temp_apk_path = BASE_DIR / "temp_unsigned.apk"

# New settings.json pointing to NCB-SPECTRA server
new_settings = {
    "sites": [
        {
            "url": "http://10.87.216.184:8000",
            "title": "NCB-SPECTRA Field Drug Testing"
        },
        {
            "url": "http://localhost:8000",
            "title": "NCB-SPECTRA Localhost"
        }
    ],
    "other": "http://10.87.216.184:8000",
    "match": [
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
    "timestamp": "2026-11-13T10:45:00Z"
}

with zipfile.ZipFile(temp_apk_path, "w", zipfile.ZIP_DEFLATED) as out_zip:
    for item in in_zip.infolist():
        # Skip old signature files
        if item.filename.startswith("META-INF/"):
            continue
        # Replace settings.json
        if item.filename == "assets/settings.json":
            out_zip.writestr(item, json.dumps(new_settings, indent=2))
        else:
            out_zip.writestr(item, in_zip.read(item.filename))

print("✓ Rebuilt APK with NCB-SPECTRA settings!")

print("Step 3: Creating RSA Keystore...")
if KEYSTORE.exists():
    KEYSTORE.unlink()

keytool_cmd = [
    str(KEYTOOL),
    "-genkey", "-noprompt",
    "-keystore", str(KEYSTORE),
    "-alias", "ncb",
    "-keyalg", "RSA",
    "-keysize", "2048",
    "-validity", "10000",
    "-storepass", "ncbspectra2026",
    "-keypass", "ncbspectra2026",
    "-dname", "CN=NCB-SPECTRA, OU=Digital Forensics, O=Narcotics Control Bureau, L=New Delhi, S=Delhi, C=IN"
]

res = subprocess.run(keytool_cmd, capture_output=True, text=True)
if res.returncode != 0:
    print("Keytool error:", res.stderr)
else:
    print("✓ Keystore generated successfully!")

print("Step 4: Signing APK with jarsigner...")
# Copy temp to final
import shutil
shutil.copyfile(temp_apk_path, OUTPUT_APK)
temp_apk_path.unlink()

jarsigner_cmd = [
    str(JARSIGNER),
    "-sigalg", "SHA256withRSA",
    "-digestalg", "SHA-256",
    "-keystore", str(KEYSTORE),
    "-storepass", "ncbspectra2026",
    "-keypass", "ncbspectra2026",
    str(OUTPUT_APK),
    "ncb"
]

res2 = subprocess.run(jarsigner_cmd, capture_output=True, text=True)
if res2.returncode != 0:
    print("Jarsigner error:", res2.stderr)
else:
    print("✓ APK signed successfully!")

# Verify signature
verify_cmd = [str(JARSIGNER), "-verify", str(OUTPUT_APK)]
res3 = subprocess.run(verify_cmd, capture_output=True, text=True)
print("Signature verification:", res3.stdout.strip())

print(f"\n========================================================")
print(f"SUCCESS: Standalone Android APK created at:")
print(f"  {OUTPUT_APK}")
print(f"Size: {OUTPUT_APK.stat().st_size:,} bytes")
print(f"========================================================")
