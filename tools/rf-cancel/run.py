#!/usr/bin/env python3
"""
rf-cancel tool - Cancel the current workflow
"""
import json
import sys
from datetime import datetime
from pathlib import Path

def main():
    # Get paths
    script_dir = Path(__file__).parent  # tools/rf-cancel
    tools_dir = script_dir.parent       # tools
    skill_dir = tools_dir.parent        # ralph-flow
    state_file = skill_dir / 'state.json'
    logs_dir = skill_dir / 'logs'

    # Check if state file exists
    if not state_file.exists():
        print(json.dumps({'error': 'No workflow state found.'}, ensure_ascii=False))
        return

    # Read state
    with open(state_file, 'r', encoding='utf-8') as f:
        state = json.load(f)

    if not state.get('active', False):
        print(json.dumps({'error': 'No active workflow to cancel.'}, ensure_ascii=False))
        return

    workflow_name = state.get('workflow_name', 'unknown')
    current_step = state.get('current_step', 'unknown')
    current_phase = state.get('current_phase', 'unknown')
    fail_count = state.get('fail_count', 0)
    user_task = state.get('user_task', '')

    # Create cancellation report
    logs_dir.mkdir(parents=True, exist_ok=True)
    report_file = logs_dir / f"cancellation-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"

    report = {
        'type': 'cancellation',
        'workflow_name': workflow_name,
        'current_step': current_step,
        'current_phase': current_phase,
        'fail_count': fail_count,
        'user_task': user_task,
        'cancelled_at': datetime.now().isoformat()
    }

    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # Clear state
    new_state = {
        'active': False,
        'workflow_name': workflow_name,
        'cancelled': True,
        'cancelled_at': datetime.now().isoformat()
    }

    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(new_state, f, ensure_ascii=False, indent=2)

    print(json.dumps({
        'success': True,
        'message': f"Workflow '{workflow_name}' cancelled.",
        'report': str(report_file)
    }, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
