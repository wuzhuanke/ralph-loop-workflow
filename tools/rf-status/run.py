#!/usr/bin/env python3
"""
rf-status tool - Show workflow status.
Returns current step, phase, fail count, step details, sub-workflow depth.
"""
import json
import sys
from pathlib import Path

# Add tools dir to path for rf_lib imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from rf_lib.paths import get_skill_dir
from rf_lib.state import read_state, get_stack_depth
from rf_lib.workflow import load_workflow, get_step, is_sub_workflow_step
from rf_lib.report import read_step_records


def main():
    skill_dir = get_skill_dir(__file__)

    # Read state
    state = read_state(skill_dir)
    if not state:
        print(json.dumps({
            'active': False,
            'message': 'No workflow state found.'
        }, ensure_ascii=False, indent=2))
        return

    if not state.get('active', False):
        print(json.dumps({
            'active': False,
            'message': 'No active workflow.',
            'last_workflow': state.get('workflow_name'),
        }, ensure_ascii=False, indent=2))
        return

    workflow_name = state.get('workflow_name', 'unknown')
    current_step_id = state.get('current_step', 'unknown')
    current_phase = state.get('current_phase', 'do')
    fail_count = state.get('fail_count', 0)
    user_task = state.get('user_task', '')
    paused = state.get('paused', False)
    last_failure = state.get('last_failure_reason')
    start_time = state.get('start_time')
    parent = state.get('parent')

    # Load workflow for step details
    workflow = load_workflow(skill_dir, workflow_name)
    step = None
    step_detail = None
    if workflow:
        step = get_step(workflow, current_step_id)
        if step:
            step_detail = {
                'id': step.get('id'),
                'desc': step.get('desc', ''),
                'do': step.get('do', ''),
                'check': step.get('check', ''),
                'input': step.get('input', ''),
                'output': step.get('output', ''),
                'on_pass': step.get('on_pass', ''),
                'on_fail': step.get('on_fail', ''),
                'max_fail_count': step.get('max_fail_count', 5),
                'is_sub_workflow': is_sub_workflow_step(step),
            }
            if is_sub_workflow_step(step):
                step_detail['sub_workflow'] = step.get('workflow')

    # Get stack depth
    stack_depth = get_stack_depth(skill_dir)

    # Get step records
    step_records = read_step_records(skill_dir)

    # Build result
    result = {
        'active': True,
        'workflow': workflow_name,
        'current_step': current_step_id,
        'current_phase': current_phase,
        'fail_count': fail_count,
        'paused': paused,
        'user_task': user_task,
        'start_time': start_time,
        'stack_depth': stack_depth,
        'step_detail': step_detail,
        'step_records': step_records,
    }

    if last_failure:
        result['last_failure_reason'] = last_failure

    if parent:
        result['parent'] = parent

    # Phase-specific guidance
    if current_phase == 'do':
        result['guidance'] = (
            '当前在 DO 阶段。请执行当前步骤的任务，'
            '完成后在回复最后一行输出 <promise>done</promise>，'
            '然后调用 rf-detect 检测标记。'
        )
    elif current_phase == 'check':
        result['guidance'] = (
            '当前在 CHECK 阶段。请调用 rf-check 获取对抗性检查提示，'
            '然后将提示传给 Task 子 agent 执行验证。'
        )

    if paused:
        result['guidance'] = (
            '工作流已暂停。请查看失败原因，修复问题后调用 rf-continue 继续，'
            '或调用 rf-cancel 取消工作流。'
        )

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
