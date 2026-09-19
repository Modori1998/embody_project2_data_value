"""Smoke selection for G1-P1 signal audit and G1-P2 boundary audit."""

from __future__ import annotations

from .config import G1P1Config
from .source import EpisodeIdentity


def select_smoke_episodes(
    identities: tuple[EpisodeIdentity, ...],
    config: G1P1Config,
) -> list[EpisodeIdentity]:
    if not identities:
        raise ValueError("no episodes available")
    by_id = {item.native_episode_key: item for item in identities}
    chosen: list[EpisodeIdentity] = []
    seen: set[str] = set()

    def add(item: EpisodeIdentity) -> None:
        if item.native_episode_key in seen:
            return
        if item.num_steps > config.max_smoke_length_frames:
            return
        chosen.append(item)
        seen.add(item.native_episode_key)

    if "demo_0" in by_id:
        add(by_id["demo_0"])
    eligible = sorted(
        [item for item in identities if item.num_steps <= config.max_smoke_length_frames],
        key=lambda item: (item.num_steps, item.episode_index),
    )
    if not eligible:
        raise ValueError("no episodes within smoke length cap")
    targets = [
        eligible[0],
        eligible[len(eligible) // 3],
        eligible[(2 * len(eligible)) // 3],
        eligible[-1],
    ]
    for item in targets:
        add(item)
        if len(chosen) >= config.smoke_episode_count:
            break
    if len(chosen) < 3:
        for item in eligible:
            add(item)
            if len(chosen) >= 3:
                break
    return chosen[: config.smoke_episode_count]


def select_g1_p2_smoke_episodes(identities: tuple[EpisodeIdentity, ...], adapter, config) -> list[EpisodeIdentity]:
    """Reuse G1-P1 demos and add at least one WORSE demo under the length cap."""

    if not identities:
        raise ValueError("no episodes available")
    by_id = {item.native_episode_key: item for item in identities}
    chosen: list[EpisodeIdentity] = []
    seen: set[str] = set()
    cap = int(config.max_smoke_length_frames)
    target = int(getattr(config, "smoke_episode_count", 6))

    def add(item: EpisodeIdentity | None) -> None:
        if item is None or item.native_episode_key in seen or item.num_steps > cap:
            return
        chosen.append(item)
        seen.add(item.native_episode_key)

    def quality(item: EpisodeIdentity) -> str:
        return str(adapter.get_weak_reference(item.source_episode_id).get("quality_bucket") or "UNKNOWN")

    for key in getattr(config, "must_include_p1_demos", ()):
        add(by_id.get(key))
    preferred = getattr(config, "preferred_worse_demo", "")
    if preferred:
        add(by_id.get(preferred))
    worse_items = sorted(
        [item for item in identities if item.num_steps <= cap and quality(item) == "WORSE"],
        key=lambda item: (item.num_steps, item.episode_index),
    )
    if getattr(config, "must_include_worse", True) and not any(quality(item) == "WORSE" for item in chosen):
        if worse_items:
            add(worse_items[0])
    for item in worse_items:
        if len(chosen) >= target:
            break
        add(item)
    if len(chosen) < target:
        extra = sorted(
            [item for item in identities if item.num_steps <= cap],
            key=lambda item: (item.num_steps, item.episode_index),
        )
        for item in extra:
            add(item)
            if len(chosen) >= target:
                break
    if not chosen:
        raise ValueError("no episodes within G1-P2 smoke length cap")
    return chosen[: max(target, 5)]
