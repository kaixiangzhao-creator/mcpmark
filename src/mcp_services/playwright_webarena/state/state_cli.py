from __future__ import annotations

import argparse
import json
from pathlib import Path

from .external_backend import ExternalStateBackend


def _backend(args: argparse.Namespace) -> ExternalStateBackend:
    return ExternalStateBackend(
        state_root=args.state_root,
        snapshot_driver=getattr(args, "snapshot_driver", "reflink"),
        media_mode=getattr(args, "media_mode", "readonly"),
        runtime_registry=getattr(args, "runtime_registry", ""),
    )


def _prepare(args: argparse.Namespace) -> int:
    prepared = _backend(args).prepare(args.profile, args.run_id)
    print(
        json.dumps(
            {
                "run_id": prepared.run_id,
                "profile": prepared.profile,
                "state_directory": str(prepared.state_directory),
                "cleanup_token": prepared.cleanup_token,
                "mounts": [
                    {
                        "source": str(mount.source),
                        "target": mount.target,
                        "readonly": mount.readonly,
                    }
                    for mount in prepared.mounts
                ],
                "environment": prepared.environment,
                "metadata": prepared.metadata,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _inspect(args: argparse.Namespace) -> int:
    state = (
        Path(args.state_root).expanduser().resolve()
        / "runs"
        / args.profile
        / args.run_id
    )
    print(json.dumps(_backend(args).inspect(state), indent=2, sort_keys=True))
    return 0


def _cleanup(args: argparse.Namespace) -> int:
    state = (
        Path(args.state_root).expanduser().resolve()
        / "runs"
        / args.profile
        / args.run_id
    )
    record = _backend(args).inspect(state)
    _backend(args).cleanup(str(record["cleanup_token"]), state)
    print(json.dumps({"cleaned": True, "state_directory": str(state)}))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage MCPMark WebArena state slots")
    parser.add_argument("--state-root", default="/srv/mcpmark-state")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--profile", required=True, choices=("reddit", "shopping", "shopping_admin"))
    prepare.add_argument("--run-id")
    prepare.add_argument("--snapshot-driver", default="reflink", choices=("reflink", "copy"))
    prepare.add_argument("--media-mode", default="readonly", choices=("readonly", "cow"))
    prepare.add_argument("--runtime-registry", default="")
    prepare.set_defaults(handler=_prepare)

    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("--profile", required=True)
    inspect.add_argument("--run-id", required=True)
    inspect.set_defaults(handler=_inspect)

    cleanup = subparsers.add_parser("cleanup")
    cleanup.add_argument("--profile", required=True)
    cleanup.add_argument("--run-id", required=True)
    cleanup.set_defaults(handler=_cleanup)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
