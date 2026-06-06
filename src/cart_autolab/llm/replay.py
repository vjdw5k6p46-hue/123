from __future__ import annotations

from pathlib import Path


class ReplayArtifactError(RuntimeError):
    pass


def load_replay_response(replay_dir: Path, *, agent_name: str, prompt_hash: str, call_id: str) -> str:
    candidates = [
        replay_dir / "agent_outputs" / agent_name / f"{prompt_hash}_raw_response.txt",
        replay_dir / "agent_outputs" / agent_name / f"{call_id}_raw_response.txt",
        replay_dir / agent_name / f"{prompt_hash}_raw_response.txt",
        replay_dir / agent_name / f"{call_id}_raw_response.txt",
        replay_dir / f"{agent_name}.json",
        replay_dir / f"{agent_name}.txt",
    ]
    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8")
    searched = "\n".join(str(path) for path in candidates)
    raise ReplayArtifactError(f"No archived replay response found for {agent_name}. Searched:\n{searched}")
