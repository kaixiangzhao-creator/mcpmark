from __future__ import annotations

import asyncio
import os
import time
import uuid
from dataclasses import dataclass

from .profiles import get_profile


@dataclass(frozen=True)
class PreparedAEnvService:
    run_id: str
    category: str
    service_id: str
    service_url: str
    pvc_name: str
    metadata: dict[str, object]


class AEnvServiceBackend:
    """Launch an official AEnv service on an externally provisioned state PVC."""

    def __init__(
        self,
        pvc_name_template: str,
        system_url: str = "",
        timeout: int = 600,
        runtime_registry: str = "",
    ) -> None:
        if "{run_id}" not in pvc_name_template:
            raise ValueError(
                "WEBARENA_AENV_PVC_NAME_TEMPLATE must include {run_id}; "
                "a shared mutable PVC cannot reset independent tasks"
            )
        self.pvc_name_template = pvc_name_template
        self.system_url = system_url or None
        self.timeout = timeout
        self.runtime_registry = runtime_registry

    @staticmethod
    def _run(coroutine):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coroutine)
        raise RuntimeError("AEnv service backend must run outside an active asyncio loop")

    def prepare(self, category: str, run_id: str | None = None) -> PreparedAEnvService:
        return self._run(self._prepare(category, run_id or uuid.uuid4().hex[:12]))

    async def _prepare(self, category: str, run_id: str) -> PreparedAEnvService:
        try:
            from aenv.client.scheduler_client import AEnvSchedulerClient
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "install shopee-aenvironment==0.1.96 to use WEBARENA_STATE_BACKEND=aenv"
            ) from exc

        api_key = os.getenv("COMPASS_ADMIN_API_KEY")
        if not api_key:
            raise RuntimeError("COMPASS_ADMIN_API_KEY is required for AEnv")
        if not self.system_url:
            try:
                from cli.cmds.service import _get_system_url
            except ModuleNotFoundError as exc:
                raise RuntimeError("official AEnv CLI system URL resolver is unavailable") from exc
            system_url = _get_system_url()
        else:
            system_url = self.system_url

        profile = get_profile(category, self.runtime_registry)
        pvc_name = self.pvc_name_template.format(category=category, run_id=run_id)
        service_name = f"mcpmark-{category.replace('_', '-')}-{run_id}".lower()[:63].rstrip("-")
        env_name = f"{profile.aenv_name}@{profile.aenv_version}"

        async with AEnvSchedulerClient(
            base_url=system_url,
            timeout=min(float(self.timeout), 90.0),
            max_retries=0,
            api_key=api_key,
        ) as client:
            service = None
            try:
                service = await client.create_env_service(
                    name=env_name,
                    service_name=service_name,
                    replicas=1,
                    pvc_name=pvc_name,
                    mount_path="/aenv-data",
                    storage_size=None,
                    port=8080,
                    cpu_request="4",
                    cpu_limit="4",
                    memory_request="8Gi",
                    memory_limit="8Gi",
                    ephemeral_storage_request="20Gi",
                    ephemeral_storage_limit="20Gi",
                )
                deadline = time.monotonic() + self.timeout
                while service.status not in {"Running", "Failed", "Terminated"}:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(
                            f"AEnv service readiness timed out: {service.id}"
                        )
                    await asyncio.sleep(2)
                    service = await client.get_env_service(service.id)
                if service.status != "Running" or not service.service_url:
                    raise RuntimeError(
                        f"AEnv service did not become usable: id={service.id}, "
                        f"status={service.status}, url={service.service_url}"
                    )

                if category in {"shopping", "shopping_admin"}:
                    public_url = service.service_url
                    await client.update_env_service(
                        service.id,
                        environment_variables={
                            "WEBARENA_PUBLIC_BASE_URL": public_url
                        },
                    )
                    while time.monotonic() < deadline:
                        await asyncio.sleep(2)
                        service = await client.get_env_service(service.id)
                        if service.status == "Running":
                            break
                    if service.status != "Running":
                        raise RuntimeError(
                            f"AEnv service URL rollout failed: {service.id}"
                        )
                    if not service.service_url:
                        service.service_url = public_url
            except Exception:
                if service is not None:
                    try:
                        await client.delete_env_service(
                            service.id, delete_storage=False
                        )
                    except Exception:
                        pass
                raise

        return PreparedAEnvService(
            run_id=run_id,
            category=category,
            service_id=service.id,
            service_url=service.service_url.rstrip("/"),
            pvc_name=pvc_name,
            metadata={
                "aenv_name": env_name,
                "service_name": service_name,
                "pvc_preprovisioned": True,
            },
        )

    def cleanup(self, service_id: str) -> None:
        self._run(self._cleanup(service_id))

    async def _cleanup(self, service_id: str) -> None:
        from aenv.client.scheduler_client import AEnvSchedulerClient

        api_key = os.getenv("COMPASS_ADMIN_API_KEY")
        if not api_key:
            raise RuntimeError("COMPASS_ADMIN_API_KEY is required for AEnv cleanup")
        if self.system_url:
            system_url = self.system_url
        else:
            from cli.cmds.service import _get_system_url

            system_url = _get_system_url()
        async with AEnvSchedulerClient(
            base_url=system_url, timeout=90, max_retries=0, api_key=api_key
        ) as client:
            deleted = await client.delete_env_service(service_id, delete_storage=False)
            if not deleted:
                raise RuntimeError(f"AEnv service deletion failed: {service_id}")
