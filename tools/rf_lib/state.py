"""State management for ralph-flow tools."""
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime


def read_state(skill_dir: Path) -> Optional[Dict[str, Any]]:
    """Read workflow state from state.json."""
    from rf_lib.paths import get_state_file
    state_file = get_state_file(skill_dir)
    if not state_file.exists():
        return None
    try:
        with open(state_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def write_state(skill_dir: Path, state: Dict[str, Any]) -> None:
    """Write workflow state to state.json."""
    from rf_lib.paths import get_state_file
    state_file = get_state_file(skill_dir)
    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def clear_state(skill_dir: Path) -> None:
    """Remove state file and stack file."""
    from rf_lib.paths import get_state_file, get_stack_file
    state_file = get_state_file(skill_dir)
    if state_file.exists():
        state_file.unlink()
    clear_stack(skill_dir)


def mark_completed(skill_dir: Path, state: Dict[str, Any]) -> None:
    """Mark workflow as completed."""
    state['active'] = False
    state['completed_at'] = datetime.now().isoformat()
    write_state(skill_dir, state)


def mark_paused(skill_dir: Path, state: Dict[str, Any]) -> None:
    """Mark workflow as paused."""
    state['paused'] = True
    write_state(skill_dir, state)


# --- State stack for sub-workflows ---

def push_state(skill_dir: Path, state: Dict[str, Any]) -> None:
    """Push current state onto the stack (for sub-workflow entry)."""
    from rf_lib.paths import get_stack_file
    stack_file = get_stack_file(skill_dir)
    stack: List[Dict] = []
    if stack_file.exists():
        try:
            with open(stack_file, 'r', encoding='utf-8') as f:
                stack = json.load(f)
        except (json.JSONDecodeError, IOError):
            stack = []
    # Remove internal fields before pushing
    state_copy = {k: v for k, v in state.items() if k != 'parent'}
    stack.append(state_copy)
    with open(stack_file, 'w', encoding='utf-8') as f:
        json.dump(stack, f, ensure_ascii=False, indent=2)


def pop_state(skill_dir: Path) -> Optional[Dict[str, Any]]:
    """Pop parent state from the stack (for sub-workflow exit)."""
    from rf_lib.paths import get_stack_file
    stack_file = get_stack_file(skill_dir)
    if not stack_file.exists():
        return None
    try:
        with open(stack_file, 'r', encoding='utf-8') as f:
            stack = json.load(f)
        if not stack:
            return None
        parent = stack.pop()
        with open(stack_file, 'w', encoding='utf-8') as f:
            json.dump(stack, f, ensure_ascii=False, indent=2)
        return parent
    except (json.JSONDecodeError, IOError):
        return None


def clear_stack(skill_dir: Path) -> None:
    """Remove the state stack file."""
    from rf_lib.paths import get_stack_file
    stack_file = get_stack_file(skill_dir)
    if stack_file.exists():
        stack_file.unlink()


def get_stack_depth(skill_dir: Path) -> int:
    """Get current sub-workflow nesting depth."""
    from rf_lib.paths import get_stack_file
    stack_file = get_stack_file(skill_dir)
    if not stack_file.exists():
        return 0
    try:
        with open(stack_file, 'r', encoding='utf-8') as f:
            stack = json.load(f)
        return len(stack)
    except (json.JSONDecodeError, IOError):
        return 0
