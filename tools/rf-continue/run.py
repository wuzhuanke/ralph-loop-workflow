#!/usr/bin/env python3
"""
rf-continue tool - Resume a paused workflow
"""
import json
import sys
from datetime import datetime
from pathlib import Path

def main():
    # Get paths
    script_dir = Path(__file__).parent  # tools/rf-continue
    tools_dir = script_dir.parent       # tools
    skill_dir = tools_dir.parent        # ralph-flow
    workflows_dir = skill_dir / 'workflows'
    state_file = skill_dir / 'state.json'

    # Check if state file exists
    if not state_file.exists():
        print(json.dumps({'error': 'No workflow state found.'}, ensure_ascii=False))
        return

    # Read state
    with open(state_file, 'r', encoding='utf-8') as f:
        state = json.load(f)

    if not state.get('active', False):
        print(json.dumps({'error': 'No active workflow to continue.'}, ensure_ascii=False))
        return

    if not state.get('paused', False):
        print(json.dumps({
            'warning': f"Workflow is not paused. Current step: {state.get('current_step')}"
        }, ensure_ascii=False))
        return

    workflow_name = state.get('workflow_name', 'unknown')
    current_step = state.get('current_step', 'unknown')
    user_task = state.get('user_task', '')
    last_failure = state.get('last_failure_reason', '')

    # Update state
    new_state = {
        'active': True,
        'workflow_name': workflow_name,
        'current_step': current_step,
        'current_phase': 'do',
        'fail_count': 0,
        'user_task': user_task,
        'paused': False,
        'last_failure_reason': None,
        'continue_time': datetime.now().isoformat()
    }

    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(new_state, f, ensure_ascii=False, indent=2)

    # Get step details
    step_details = {'id': current_step, 'desc': ''}
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
                            'id': current_step,
                            'desc': step.get('desc', '')
                        }
                        break
            except:
                pass
            break

    # Build response
    result = {
        'success': True,
        'message': f"Workflow '{workflow_name}' resumed.",
        'current_step': step_details,
        'do_instruction': 'Execute the task and output <promise>done</promise> when complete.'
    }

    if last_failure:
        result['previous_failure_reason'] = last_failure

    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
