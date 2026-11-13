"""
Server Runner for NCB Field Drug Testing Digital Companion.
Starts Uvicorn server and prints local & local network IP addresses for mobile testing.
"""

import socket
import uvicorn
import config

def get_local_ip():
    """Gets local LAN IP address of this computer."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

if __name__ == "__main__":
    local_ip = get_local_ip()
    port = config.PORT

    print("=" * 65)
    print("  NARCOTICS CONTROL BUREAU - FIELD DRUG TESTING COMPANION")
    print("  Problem ID: 26231 | Ministry of Home Affairs")
    print("=" * 65)
    print(f"  > Desktop Local:    http://localhost:{port}")
    print(f"  > Mobile on Wi-Fi:  http://{local_ip}:{port}")
    print(f"  > Database Backend: {'Supabase Cloud' if config.is_supabase_configured() else 'Local SQLite Fallback'}")
    print("=" * 65)
    print("  Press Ctrl+C to stop the server.\n")

    uvicorn.run("main:app", host=config.HOST, port=port, reload=True)

