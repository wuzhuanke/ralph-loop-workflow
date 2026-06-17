"""Path constants and helpers for ralph-flow tools."""
from pathlib import Path
from typing import Optional


def get_skill_dir(tool_file: str) -> Path:
    """Get skill root directory from a tool's run.py location.
    Assumes tool is at <skill_dir>/tools/<tool_name>/run.py
    """
    return Path(tool_file).parent.parent.parent


def get_workflows_dir(skill_dir: Path) -> Path:
    return skill_dir / 'workflows'


def get_state_file(skill_dir: Path) -> Path:
    return skill_dir / 'state.json'


def get_stack_file(skill_dir: Path) -> Path:
    return skill_dir / 'state_stack.json'


def get_logs_dir(skill_dir: Path) -> Path:
    return skill_dir / 'logs'


def get_step_records_file(skill_dir: Path) -> Path:
    return skill_dir / 'step_records.json'
