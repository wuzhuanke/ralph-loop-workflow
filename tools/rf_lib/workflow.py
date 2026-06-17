"""Workflow loading and parsing for ralpha-loop-workflow tools."""
import json
from pathlib import Path
from typing import Optional, Dict, Any, List


def _try_import_yaml():
    """Try to import yaml, return None if not available."""
    try:
        import yaml
        return yaml
    except ImportError:
        return None


def parse_workflow_file(file_path: Path, workflow_name: str) -> Optional[Dict[str, Any]]:
    """Parse a workflow YAML file and return the workflow definition."""
    yaml = _try_import_yaml()
    if yaml is None:
        return _parse_yaml_fallback(file_path, workflow_name)

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            parsed = yaml.safe_load(f)
    except Exception:
        return None

    if not parsed or not isinstance(parsed, dict):
        return None

    steps = parsed.get('steps', [])
    if not steps or not isinstance(steps, list):
        return None

    # Validate steps
    valid_steps = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        if not step.get('id') or not step.get('on_pass') or not step.get('on_fail'):
            continue
        if not isinstance(step.get('max_fail_count', 0), int) or step.get('max_fail_count', 0) < 1:
            step['max_fail_count'] = 5
        valid_steps.append(step)

    if not valid_steps:
        return None

    # Parse adversarial_check config
    adv = parsed.get('adversarial_check')
    adversarial_check = None
    if adv and isinstance(adv, dict):
        adversarial_check = {
            'system_prompt': adv.get('system_prompt'),
            'timeout_ms': adv.get('timeout_ms'),
            'agent': adv.get('agent'),
        }

    # Parse manual_step
    manual_step_raw = parsed.get('manual_step', '')
    if isinstance(manual_step_raw, str):
        manual_step = [s.strip() for s in manual_step_raw.split(',') if s.strip()]
    elif isinstance(manual_step_raw, list):
        manual_step = manual_step_raw
    else:
        manual_step = []

    return {
        'name': workflow_name,
        'description': parsed.get('description', ''),
        'manual_step': manual_step,
        'steps': valid_steps,
        'adversarial_check': adversarial_check,
    }


def _parse_yaml_fallback(file_path: Path, workflow_name: str) -> Optional[Dict[str, Any]]:
    """Fallback YAML parser when pyyaml is not available."""
    try:
        content = file_path.read_text(encoding='utf-8')
    except IOError:
        return None

    # Very basic step extraction
    steps = []
    current_step = None
    for line in content.split('\n'):
        stripped = line.strip()
        if stripped.startswith('- id:'):
            if current_step:
                steps.append(current_step)
            current_step = {'id': stripped.split(':', 1)[1].strip(), 'max_fail_count': 5}
        elif current_step:
            if stripped.startswith('desc:'):
                current_step['desc'] = stripped.split(':', 1)[1].strip()
            elif stripped.startswith('do:'):
                current_step['do'] = stripped.split(':', 1)[1].strip()
            elif stripped.startswith('on_pass:'):
                current_step['on_pass'] = stripped.split(':', 1)[1].strip()
            elif stripped.startswith('on_fail:'):
                current_step['on_fail'] = stripped.split(':', 1)[1].strip()
    if current_step:
        steps.append(current_step)

    if not steps:
        return None

    return {
        'name': workflow_name,
        'description': '',
        'manual_step': [],
        'steps': steps,
        'adversarial_check': None,
    }


def load_workflow(skill_dir: Path, workflow_name: str) -> Optional[Dict[str, Any]]:
    """Load a workflow by name. Searches skill workflows/ directory."""
    from rf_lib.paths import get_workflows_dir
    workflows_dir = get_workflows_dir(skill_dir)

    for ext in ['.yaml', '.yml']:
        candidate = workflows_dir / f"{workflow_name}{ext}"
        if candidate.exists():
            result = parse_workflow_file(candidate, workflow_name)
            if result:
                return result

    return None


def get_step(workflow: Dict[str, Any], step_id: str) -> Optional[Dict[str, Any]]:
    """Get a step definition by ID."""
    for step in workflow.get('steps', []):
        if step.get('id') == step_id:
            return step
    return None


def is_sub_workflow_step(step: Dict[str, Any]) -> bool:
    """Check if a step is a sub-workflow step (has 'workflow' field)."""
    return 'workflow' in step and isinstance(step.get('workflow'), str)


def list_workflows(skill_dir: Path) -> List[Dict[str, str]]:
    """List all available workflows."""
    from rf_lib.paths import get_workflows_dir
    workflows_dir = get_workflows_dir(skill_dir)

    if not workflows_dir.exists():
        return []

    workflows = []
    for f in workflows_dir.iterdir():
        if f.suffix in ['.yaml', '.yml']:
            name = f.stem
            desc = name
            # Try to read description
            wf = parse_workflow_file(f, name)
            if wf:
                desc = wf.get('description', name)
            workflows.append({'name': name, 'description': desc})

    return workflows
