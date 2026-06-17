#!/usr/bin/env python3
"""
rf-status tool - Show workflow status
"""
import json
import sys
from pathlib import Path

def main():
    # Get paths
    script_dir = Path(__file__).parent  # tools/rf-status
    tools_dir = script_dir.parent       # tools
    skill_dir = tools_dir.parent        # ralph-flow
    workflows_dir = skill_dir / 'workflows'
    state_file = skill_dir / 'state.json'

    # Check if state file exists
    if not state_file.exists():
        print(json.dumps({
            'status': 'no_workflow',
            'message': 'No workflow state found.'
        }, ensure_ascii=False))
        return

    # Read state
    with open(state_file, 'r', encoding='utf-8') as f:
        state = json.load(f)

    if not state.get('active', False):
        print(json.dumps({
            'status': 'inactive',
            'message': f"Workflow '{state.get('workflow_name', 'unknown')}' is not active (completed/cancelled)."
        }, ensure_ascii=False))
        return

    workflow_name = state.get('workflow_name', 'unknown')
    current_step = state.get('current_step', 'unknown')
    current_phase = state.get('current_phase', 'unknown')
    fail_count = state.get('fail_count', 0)
    user_task = state.get('user_task', '')
    paused = state.get('paused', False)
    last_failure = state.get('last_failure_reason', '')

    # Try to get step details from workflow file
    step_details = {'desc': '', 'do': '', 'check': ''}
    for ext in ['.yaml', '.yml']:
        workflow_file = workflows_dir / f"{workflow_name}{ext}"
        if workflow_file.exists():
            try:
                import yaml
                with open(workflow_file, 'r', encoding='utf-8') as f:
                    workflow_def = yaml.safe_load(f)
                for step in workflow_def.get('steps', []):
                    if step.get('id') == current_step:
                        step_details = {
                            'desc': step.get('desc', ''),
                            'do': step.get('do', ''),
                            'check': step.get('check', '')
                        }
                        break
            except:
                pass
            break

    # Build response
    result = {
        'status': 'active',
        'workflow_name': workflow_name,
        'current_step': current_step,
        'current_phase': current_phase,
        'fail_count': fail_count,
        'user_task': user_task,
        'paused': paused,
        'step_details': step_details
    }

    if last_failure:
        result['last_failure_reason'] = last_failure

    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
