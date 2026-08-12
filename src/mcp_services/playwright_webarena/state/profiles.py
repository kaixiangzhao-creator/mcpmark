from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StateProfile:
    name: str
    baseline_directory: str
    mutable_directories: tuple[str, ...]
    media_directory: str
    runtime_image: str
    aenv_name: str
    aenv_version: str = "2.0.0"


PROFILES = {
    "reddit": StateProfile(
        name="reddit",
        baseline_directory="postmill-v1-pristine",
        mutable_directories=("postgres",),
        media_directory="submission_images",
        runtime_image="ai-01.my.harbor.shopeemobile.com/ai-infra/postmill-populated-exposed-withimg:2.0.0",
        aenv_name="postmill-populated-exposed-withimg",
    ),
    "shopping": StateProfile(
        name="shopping",
        baseline_directory="shopping-v1-pristine",
        mutable_directories=("mysql", "elasticsearch"),
        media_directory="media",
        runtime_image="ai-01.my.harbor.shopeemobile.com/ai-infra/shopping-final-0712:2.0.0",
        aenv_name="shopping-final-0712",
    ),
    "shopping_admin": StateProfile(
        name="shopping_admin",
        baseline_directory="shopping-admin-v1-pristine",
        mutable_directories=("mysql", "elasticsearch"),
        media_directory="media",
        runtime_image="ai-01.my.harbor.shopeemobile.com/ai-infra/shopping-admin-final-0719:2.0.0",
        aenv_name="shopping-admin-final-0719",
    ),
}


def get_profile(category: str, runtime_registry: str = "") -> StateProfile:
    try:
        profile = PROFILES[category]
    except KeyError as exc:
        raise ValueError(f"unsupported WebArena category: {category}") from exc

    if not runtime_registry:
        return profile
    image_leaf = profile.runtime_image.rsplit("/", 1)[-1]
    return StateProfile(
        **{**profile.__dict__, "runtime_image": f"{runtime_registry.rstrip('/')}/{image_leaf}"}
    )
