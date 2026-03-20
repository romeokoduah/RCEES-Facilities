#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════════════╗
║  RCEES FACILITIES MANAGEMENT SYSTEM v3.0                         ║
║  Regional Centre for Energy & Environmental Sustainability       ║
║  University of Energy and Natural Resources, Sunyani             ║
╠═══════════════════════════════════════════════════════════════════╣
║  → http://localhost:8000                                         ║
║  Admin: admin@rcees.uenr.edu.gh / rcees2024                     ║
╚═══════════════════════════════════════════════════════════════════╝

Run with:
    python run.py

Or from Jupyter:
    %run run.py
"""
import os, sys, subprocess, signal, time

# ── Ensure we're in the project directory ──
try:
    PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    PROJECT_DIR = os.getcwd()

os.chdir(PROJECT_DIR)
sys.path.insert(0, PROJECT_DIR)

# ── Install dependencies if missing ──
try:
    import fastapi, uvicorn, nest_asyncio
except ImportError:
    print("\n⚡ Installing dependencies...")
    os.system(f"{sys.executable} -m pip install -r requirements.txt -q")
    import uvicorn, nest_asyncio

PORT = 8000

# ── Kill any previous server on this port ──
try:
    result = subprocess.run(["lsof", "-ti", f":{PORT}"], capture_output=True, text=True)
    for pid in result.stdout.strip().split("\n"):
        if pid.strip():
            try:
                os.kill(int(pid.strip()), signal.SIGKILL)
                print(f"  🔄 Killed old process on port {PORT} (PID {pid.strip()})")
            except (ProcessLookupError, ValueError):
                pass
    time.sleep(0.5)
except FileNotFoundError:
    # lsof not available (Windows) — try netstat approach
    try:
        result = subprocess.run(
            f"netstat -ano | findstr :{PORT}",
            shell=True, capture_output=True, text=True
        )
        for line in result.stdout.strip().split("\n"):
            parts = line.split()
            if parts and parts[-1].isdigit():
                try:
                    os.kill(int(parts[-1]), signal.SIGTERM)
                except:
                    pass
        time.sleep(0.5)
    except:
        pass

# ── Patch event loop for Jupyter ──
try:
    import asyncio
    asyncio.get_running_loop()
    import nest_asyncio
    nest_asyncio.apply()
    print("  📓 Jupyter detected — event loop patched")
except RuntimeError:
    pass  # Normal script execution, no running loop

# ── Initialize database ──
from backend.database import init_db

print(r"""
╔═══════════════════════════════════════════════════════════════════╗
║   🏢  RCEES FACILITIES MANAGEMENT SYSTEM v3.0                    ║
║   Regional Centre for Energy & Environmental Sustainability       ║
║   University of Energy and Natural Resources (UENR)               ║
╠═══════════════════════════════════════════════════════════════════╣
║   🌐  http://localhost:8000                                       ║
║   📧  Admin: admin@rcees.uenr.edu.gh                              ║
║   🔑  Password: rcees2024                                         ║
╠═══════════════════════════════════════════════════════════════════╣
║   ✅ 18 facilities (4 labs, 4 lecture, 3 seminar, studio, etc.)  ║
║   ✅ Real-time calendar slot booking with weekend pricing         ║
║   ✅ Guest booking with RCEES-XXXXX reference tracking            ║
║   ✅ Admin dashboard with revenue analytics & occupancy           ║
║   ✅ Facility onboarding with photo/video uploads                 ║
║   ✅ Maintenance scheduling that blocks bookings                  ║
║   ✅ 7 discount codes with smart validation                       ║
║   ✅ Tiered pricing (hourly / half-day / full-day)                ║
║   ✅ Weekend 1.5× rate multiplier                                 ║
║   ✅ Payment gateway (MoMo / Card / Cash)                         ║
║   ✅ 10 equipment rental add-ons                                  ║
║   ✅ 4-tier role system (admin/manager/staff/user)                ║
║   ✅ Reviews, ratings & conflict detection                        ║
╚═══════════════════════════════════════════════════════════════════╝
""")

init_db()

# ── Start server ──
print(f"  🚀 Starting server on http://localhost:{PORT}")
print(f"  ⏹  Press Ctrl+C to stop\n")

import uvicorn
uvicorn.run("backend.app:app", host="0.0.0.0", port=PORT, log_level="info", reload=False)
