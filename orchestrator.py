#!/usr/bin/env python3
"""
Mini Menu Platform Master Orchestrator
Concurrently spawns, monitors, and gracefully shuts down all 4 microservices:
  1. mini-menu-auth-service    (Port 8001)
  2. mini-menu-catalog-service (Port 8002)
  3. mini-menu-order-service   (Port 8003)
  4. mini-menu-api-gateway     (Port 8000)
"""

import asyncio
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Dict, List
import urllib.request

# Base directory locating the 4 service repositories
PROJECT_ROOT = Path(__file__).resolve().parent
# If running from inside mini-menu-api-gateway/, project root is parent
if (PROJECT_ROOT / "mini-menu-auth-service").is_dir():
    ROOT_DIR = PROJECT_ROOT
elif (PROJECT_ROOT.parent / "mini-menu-auth-service").is_dir():
    ROOT_DIR = PROJECT_ROOT.parent
else:
    ROOT_DIR = PROJECT_ROOT

SERVICES = [
    {
        "name": "mini-menu-auth-service",
        "dir": ROOT_DIR / "mini-menu-auth-service",
        "port": 8001,
        "health": "http://127.0.0.1:8001/api/v1/auth/health",
    },
    {
        "name": "mini-menu-catalog-service",
        "dir": ROOT_DIR / "mini-menu-catalog-service",
        "port": 8002,
        "health": "http://127.0.0.1:8002/api/v1/catalog/health",
    },
    {
        "name": "mini-menu-order-service",
        "dir": ROOT_DIR / "mini-menu-order-service",
        "port": 8003,
        "health": "http://127.0.0.1:8003/api/v1/orders/health",
    },
    {
        "name": "mini-menu-api-gateway",
        "dir": ROOT_DIR / "mini-menu-api-gateway",
        "port": 8000,
        "health": "http://127.0.0.1:8000/health",
    },
]

processes: List[subprocess.Popen] = []


def is_service_healthy(url: str, timeout: float = 1.5) -> bool:
    """Checks if a service returns HTTP 200 on its health endpoint."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MiniMenuOrchestrator"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def terminate_all_services(signum=None, frame=None):
    """Gracefully terminates all child microservice processes."""
    print("\n🛑 Initiating graceful shutdown of all microservices...")
    for proc in processes:
        if proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass

    # Allow 2 seconds for graceful shutdown
    time.sleep(1.5)

    for proc in processes:
        if proc.poll() is None:
            try:
                proc.kill()
            except Exception:
                pass

    print("✅ All services shut down successfully. Goodbye!\n")
    sys.exit(0)


def start_services():
    """Starts all microservices concurrently and initiates liveness monitoring."""
    signal.signal(signal.SIGINT, terminate_all_services)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, terminate_all_services)

    print("=" * 70)
    print("🚀 MINI MENU MICROSERVICES PLATFORM ORCHESTRATOR")
    print("=" * 70)

    # 1. Start each service subprocess
    for svc in SERVICES:
        svc_dir = svc["dir"]
        run_file = svc_dir / "run.py"
        if not run_file.exists():
            print(f"⚠️  Missing {run_file}, skipping {svc['name']}")
            continue

        print(f"▶️  Launching {svc['name']} on port {svc['port']}...")
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        proc = subprocess.Popen(
            [sys.executable, str(run_file)],
            cwd=str(svc_dir),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
        processes.append(proc)

    print("-" * 70)
    print("⏳ Waiting for all services to pass initial health checks...")

    # 2. Wait up to 30 seconds for all services to become healthy
    all_ready = False
    for attempt in range(1, 31):
        statuses = [is_service_healthy(svc["health"]) for svc in SERVICES]
        ready_count = sum(statuses)
        if ready_count == len(SERVICES):
            all_ready = True
            break
        time.sleep(1)
        print(f"   [{attempt}/30s] Ready: {ready_count}/{len(SERVICES)} services online...", end="\r")

    print("\n" + "=" * 70)
    if all_ready:
        print("🎉 ALL 4 MINI MENU MICROSERVICES ARE OPERATIONAL & HEALTHY!")
    else:
        print("⚠️  Some services took longer to initialize. Current status:")
    print("=" * 70)

    for svc in SERVICES:
        status_symbol = "🟢" if is_service_healthy(svc["health"]) else "🔴"
        print(f"  {status_symbol} {svc['name']:<28} -> http://localhost:{svc['port']} (Health: {svc['health']})")

    print("=" * 70)
    print("🌐 UNIFIED API GATEWAY: http://localhost:8000")
    print("📖 GATEWAY SWAGGER UI: http://localhost:8000/docs")
    print("Press Ctrl+C to terminate all services.")
    print("=" * 70)

    # 3. Keep main process alive and monitor child processes
    try:
        while True:
            for i, proc in enumerate(processes):
                if proc.poll() is not None:
                    svc = SERVICES[i]
                    print(f"⚠️  {svc['name']} exited unexpectedly with code {proc.returncode}")
            time.sleep(5)
    except KeyboardInterrupt:
        terminate_all_services()


if __name__ == "__main__":
    start_services()
