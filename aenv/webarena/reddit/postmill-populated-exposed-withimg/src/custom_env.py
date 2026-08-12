import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict

from aenv import register_health, register_reward, register_tool


def _web_status() -> Dict[str, Any]:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8080/", timeout=5) as response:
            return {"reachable": True, "status_code": response.status}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"reachable": False, "error": str(exc)}


def _services() -> Dict[str, Any]:
    completed = subprocess.run(
        ["supervisorctl", "status"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    required = ("aenv", "nginx", "php-fpm", "postgres")
    lines = completed.stdout.splitlines()
    healthy = all(
        any(line.startswith(name) and "RUNNING" in line for line in lines)
        for name in required
    )
    return {
        "ok": healthy,
        "returncode": completed.returncode,
        "status": completed.stdout,
        "error": completed.stderr,
    }


@register_health
def check_health() -> Dict[str, Any]:
    web = _web_status()
    services = _services()
    data_root = Path("/aenv-data")
    data_ready = all(
        (data_root / name).is_dir() for name in ("postgres", "submission_images")
    )
    healthy = bool(web.get("reachable")) and bool(services.get("ok")) and data_ready
    return {
        "status": "healthy" if healthy else "degraded",
        "web": web,
        "services": services,
        "external_data_ready": data_ready,
    }


@register_tool
def webarena_status() -> Dict[str, Any]:
    """Return read-only Postmill service and external-state readiness."""
    return check_health()


@register_reward
def webarena_reward(task: str = "postmill-health") -> Dict[str, Any]:
    health = check_health()
    healthy = health.get("status") == "healthy"
    return {
        "task_name": task,
        "status": "success" if healthy else "failed",
        "score": 1.0 if healthy else 0.0,
        "raw_output": health,
    }
