import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse

from aenv import register_health, register_reward, register_tool


def _web_status() -> Dict[str, Any]:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8080/", timeout=3) as response:
            return {"reachable": True, "status_code": response.status}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"reachable": False, "error": str(exc)}


@register_health
def check_health() -> Dict[str, Any]:
    services = subprocess.run(
        ["supervisorctl", "status"], capture_output=True, text=True, check=False
    )
    web = _web_status()
    data_root = Path("/aenv-data")
    data_ready = all(
        (data_root / name).is_dir() for name in ("mysql", "media", "elasticsearch")
    )
    healthy = services.returncode == 0 and bool(web.get("reachable")) and data_ready
    return {
        "status": "healthy" if healthy else "degraded",
        "web": web,
        "external_data_ready": data_ready,
        "services": services.stdout,
        "service_error": services.stderr,
    }


@register_tool
def webarena_status() -> Dict[str, Any]:
    """Return read-only WebArena service and external-state readiness."""
    return check_health()


@register_tool
def configure_public_url(base_url: str) -> Dict[str, Any]:
    """Set Magento links to the public URL assigned to this AEnv service."""
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return {"ok": False, "error": "base_url must be an absolute HTTP(S) URL"}

    normalized = base_url.rstrip("/") + "/"
    commands = (
        ["php", "bin/magento", "config:set", "web/unsecure/base_url", normalized],
        ["php", "bin/magento", "config:set", "web/secure/base_url", normalized],
        ["php", "bin/magento", "cache:flush"],
    )
    output = []
    for command in commands:
        completed = subprocess.run(
            command,
            cwd="/var/www/magento2",
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        output.append(
            {
                "command": command[2:],
                "returncode": completed.returncode,
                "stdout": completed.stdout[-2000:],
                "stderr": completed.stderr[-2000:],
            }
        )
        if completed.returncode != 0:
            return {"ok": False, "base_url": normalized, "steps": output}
    return {"ok": True, "base_url": normalized, "steps": output}


@register_reward
def webarena_reward(task: str = "shopping-admin-health") -> Dict[str, Any]:
    health = check_health()
    healthy = health.get("status") == "healthy"
    return {
        "task_name": task,
        "status": "success" if healthy else "failed",
        "score": 1.0 if healthy else 0.0,
        "raw_output": health,
    }
