from pathlib import Path
from typing import Dict

from aenv import register_function, register_reward


@register_function
def image_info() -> Dict[str, object]:
    testbed = Path("/home/user/sweb/testbed")
    conda = Path("/opt/miniconda3")
    return {
        "testbed_exists": testbed.exists(),
        "testbed_path": str(testbed),
        "testbed_entries": sorted(p.name for p in testbed.iterdir())[:20] if testbed.exists() else [],
        "conda_exists": conda.exists(),
        "conda_path": str(conda),
    }


@register_function
def repo_listing(path: str = "/home/user/sweb/testbed", limit: int = 50) -> Dict[str, object]:
    target = Path(path)
    if not target.exists():
        return {"path": str(target), "exists": False, "entries": []}
    entries = sorted(p.name for p in target.iterdir())[:max(limit, 0)]
    return {"path": str(target), "exists": True, "entries": entries}


@register_reward
def basic_health(task: str = "sweb-sandbox") -> Dict[str, object]:
    return {
        "task_name": task,
        "status": "success",
        "score": 1.0 if Path("/home/user/sweb/testbed").exists() else 0.0,
        "raw_output": "testbed copied from source image",
    }

