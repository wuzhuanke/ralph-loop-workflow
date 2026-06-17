#!/usr/bin/env python3
"""
rf-start tool - Start a workflow
"""
import json
import sys
import os
from datetime import datetime
from pathlib import Path

def main():
    # Read input from stdin
    input_data = json.load(sys.stdin)
    workflow = input_data.get('workflow', '')
    task = input_data.get('task', '')

    # Get paths
    script_dir = Path(__file__).parent  # tools/rf-start
    tools_dir = script_dir.parent       # tools
    skill_dir = tools_dir.parent        # ralph-flow
    workflows_dir = skill_dir / 'workflows'
    state_file = skill_dir / 'state.json'

    # Check if there's an active workflow
    if state_file.exists():
        with open(state_file, 'r', encoding='utf-8') as f:
            state = json.load(f)
        if state.get('active', False):
            print(json.dumps({
                'error': f"There is an active workflow '{state.get('workflow_name')}' "
                        f"(step: {state.get('current_step')}, phase: {state.get('current_phase')}). "
                        f"Use rf-continue to resume or rf-cancel to cancel."
            }, ensure_ascii=False))
            return

    # Find workflow file
    workflow_file = None
    for ext in ['.yaml', '.yml']:
        candidate = workflows_dir / f"{workflow}{ext}"
        if candidate.exists():
            workflow_file = candidate
            break

    if not workflow_file:
        # List available workflows
        available = []
        for f in workflows_dir.iterdir():
            if f.suffix in ['.yaml', '.yml']:
                name = f.stem
                desc = name
                # Try to read description from file
                try:
                    content = f.read_text(encoding='utf-8')
                    for line in content.split('\n'):
                        if line.startswith('description:'):
                            desc = line.split(':', 1)[1].strip()
                            break
                except:
                    pass
                available.append({'name': name, 'description': desc})

        if available:
            print(json.dumps({
                'error': f"Workflow '{workflow}' not found. Available workflows:",
                'workflows': available
            }, ensure_ascii=False, indent=2))
        else:
            print(json.dumps({
                'error': f"Workflow '{workflow}' not found. No workflows available in {workflows_dir}"
            }, ensure_ascii=False))
        return

    # Parse workflow YAML (simplified)
    try:
        import yaml
        with open(workflow_file, 'r', encoding='utf-8') as f:
            workflow_def = yaml.safe_load(f)
    except ImportError:
        # Fallback: simple parsing without yaml library
        content = workflow_file.read_text(encoding='utf-8')
        workflow_def = {'steps': []}
        # Simple step extraction
        current_step = None
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('- id:'):
                if current_step:
                    workflow_def['steps'].append(current_step)
                current_step = {'id': line.split(':', 1)[1].strip()}
            elif current_step:
                if line.startswith('desc:'):
                    current_step['desc'] = line.split(':', 1)[1].strip()
                elif line.startswith('do:'):
                    current_step['do'] = line.split(':', 1)[1].strip()
        if current_step:
            workflow_def['steps'].append(current_step)

    # Get first step
    steps = workflow_def.get('steps', [])
    if not steps:
        print(json.dumps({'error': 'Workflow has no steps defined'}, ensure_ascii=False))
        return

    first_step = steps[0]

    # Create state file
    new_state = {
        'active': True,
        'workflow_name': workflow,
        'current_step': first_step.get('id', 'unknown'),
        'current_phase': 'do',
        'fail_count': 0,
        'user_task': task,
        'paused': False,
        'last_failure_reason': None,
        'start_time': datetime.now().isoformat()
    }

    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(new_state, f, ensure_ascii=False, indent=2)

    # Return success
    result = {
        'success': True,
        'message': f"Workflow '{workflow}' started.",
        'task': task,
        'first_step': {
            'id': first_step.get('id', 'unknown'),
            'desc': first_step.get('desc', '')
        },
        'do_instruction': 'Execute the task and output <promise>done</promise> when complete.'
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
