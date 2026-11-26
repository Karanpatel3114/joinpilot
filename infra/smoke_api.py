"""Smoke-test a running JoinPilot API end to end (standard library only).

    python infra/smoke_api.py http://localhost:8000

Creates a project, loads the ERP sample, starts a run, approves the recommended joins
and checks that the model is built, every check passes and the dashboard has KPIs.
Exits non-zero with the reason on any failure. Used by CI against the Docker image
and, after deploys, against production.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

REQUIREMENT = "Open receivables by customer and aging bucket"


def call(base: str, method: str, path: str, body: Any = None) -> Any:
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        base + path, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read())


def wait(base: str, run_id: str, statuses: set[str], seconds: int = 180) -> dict[str, Any]:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        run: dict[str, Any] = call(base, "GET", f"/runs/{run_id}")
        if run["status"] in statuses | {"failed"}:
            return run
        time.sleep(1)
    raise SystemExit(f"run {run_id} did not reach {statuses} in {seconds}s")


def main(base: str) -> None:
    base = base.rstrip("/")
    assert call(base, "GET", "/health")["status"] == "ok"
    project = call(base, "POST", "/projects", {"name": "Smoke test"})
    tables = call(base, "POST", f"/projects/{project['id']}/tables", {"sample": "erp_s1_sap"})
    logger.info(f"loaded {len(tables)} tables")
    run = call(base, "POST", f"/projects/{project['id']}/runs", {"requirement": REQUIREMENT})
    run = wait(base, run["run_id"], {"awaiting_approval"})
    proposals = call(base, "GET", f"/runs/{run['run_id']}/proposals")
    decisions = [
        {"edge_id": p["edge_id"], "action": "approve" if p["recommended"] else "reject"}
        for p in proposals
    ]
    call(base, "POST", f"/runs/{run['run_id']}/approvals", {"decisions": decisions})
    run = wait(base, run["run_id"], {"completed"})
    if run["status"] != "completed":
        raise SystemExit(f"run failed: {run.get('error')}")
    checks = call(base, "GET", f"/runs/{run['run_id']}/checks")
    failed = [c["check_id"] for c in checks if not c["passed"]]
    metrics = call(base, "GET", f"/projects/{project['id']}/dashboard")["metrics"]
    logger.info(f"{len(checks) - len(failed)}/{len(checks)} checks passed, {len(metrics)} KPIs")
    if failed or not checks or not metrics:
        raise SystemExit(f"smoke test failed: failing checks {failed}, {len(metrics)} KPIs")
    logger.info("smoke test passed")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000")
