"""Shared utilities for the skill training framework."""
import json
from pathlib import Path


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def next_iteration_dir(workspace_root, skill_name):
    """Find iteration-N+1 dir for the skill (creates parent if needed)."""
    skill_ws = Path(workspace_root) / skill_name
    skill_ws.mkdir(parents=True, exist_ok=True)
    existing = sorted(
        [int(p.name.split("-")[1]) for p in skill_ws.glob("iteration-*") if p.is_dir()]
    )
    n = (existing[-1] + 1) if existing else 1
    d = skill_ws / f"iteration-{n}"
    d.mkdir(parents=True, exist_ok=True)
    return d, n


def latest_iteration_dir(workspace_root, skill_name):
    """Return the most recent iteration dir, or None."""
    skill_ws = Path(workspace_root) / skill_name
    if not skill_ws.exists():
        return None
    iters = sorted(
        skill_ws.glob("iteration-*"),
        key=lambda p: int(p.name.split("-")[1]),
    )
    return iters[-1] if iters else None


def previous_iteration_dir(workspace_root, skill_name):
    """Return the second-most-recent iteration dir, or None."""
    skill_ws = Path(workspace_root) / skill_name
    if not skill_ws.exists():
        return None
    iters = sorted(
        skill_ws.glob("iteration-*"),
        key=lambda p: int(p.name.split("-")[1]),
    )
    return iters[-2] if len(iters) >= 2 else None


def load_skill_md(skills_dir, skill_name):
    path = Path(skills_dir) / skill_name / "SKILL.md"
    if not path.exists():
        raise FileNotFoundError(f"SKILL.md not found at {path}")
    return path.read_text(encoding="utf-8")


def load_evals(skills_dir, skill_name):
    path = Path(skills_dir) / skill_name / "evals" / "evals.json"
    if not path.exists():
        raise FileNotFoundError(
            f"evals.json not found at {path}. Run: make init SKILL={skill_name}"
        )
    return load_json(path)
