#!/usr/bin/env python3
"""
rf-cancel tool - Cancel the current workflow.
Generates a cancellation report and cleans up state.
"""
import json
import sys
from pathlib import Path

# Add tools dir to path for rf_lib imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from rf_lib.paths import get_skill_dir
from rf_lib.state import read_state, clear_state
from rf_lib.logging import log_workflow_cancelled, log_error
from rf_lib.report import (
    read_step_records, generate_cancel_report
)


def main():
    skill_dir = get_skill_dir(__file__)

    # Read optional input
    try:
        input_data = json.load(sys.stdin)
    except Exception:
        input_data = {}

    reason = input_data.get('reason', '用户取消')

    # Read state
    state = read_state(skill_dir)
    if not state:
        print(json.dumps({'error': 'No workflow state found.'}, ensure_ascii=False))
        return

    if not state.get('active', False):
        print(json.dumps({'error': 'No active workflow to cancel.'}, ensure_ascii=False))
        return

    workflow_name = state.get('workflow_name', 'unknown')
    current_step_id = state.get('current_step', 'unknown')
    current_phase = state.get('current_phase', 'do')
    fail_count = state.get('fail_count', 0)

    # Log cancellation
    log_workflow_cancelled(skill_dir, workflow_name, reason)

    # Generate cancellation report
    step_records = read_step_records(skill_dir)
    report_path = generate_cancel_report(
        skill_dir, workflow_name,
        reason=reason,
        current_step=current_step_id,
        current_phase=current_phase,
        fail_count=fail_count,
        steps=step_records
    )

    # Clear state
    clear_state(skill_dir)

    # Return result
    result = {
        'success': True,
        'message': f"Workflow '{workflow_name}' cancelled.",
        'reason': reason,
        'cancelled_at': {
            'step': current_step_id,
            'phase': current_phase,
            'fail_count': fail_count,
        },
        'report': str(report_path),
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
