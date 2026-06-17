#!/usr/bin/env python3
"""Unit tests for rf_lib modules."""
import json
import sys
import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# Add tools dir to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'tools'))

from rf_lib.paths import (
    get_skill_dir, get_workflows_dir, get_state_file,
    get_stack_file, get_logs_dir, get_step_records_file
)
from rf_lib.state import (
    read_state, write_state, clear_state, mark_completed, mark_paused,
    push_state, pop_state, clear_stack, get_stack_depth
)
from rf_lib.workflow import (
    load_workflow, get_step, is_sub_workflow_step, list_workflows
)
from rf_lib.tags import detect_done_tag, detect_check_tag
from rf_lib.logging import (
    log_event, log_step_event, log_workflow_start, log_workflow_end,
    log_step_start, log_done_detected, log_check_result, log_info
)
from rf_lib.report import (
    create_step_record, read_step_records, write_step_records,
    append_step_record, clear_step_records, generate_completion_report,
    generate_cancel_report, generate_pause_report
)

PASS = 0
FAIL = 0


def test(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} {detail}")


def setup_test_env():
    """Create a temporary skill directory with workflows."""
    tmp = Path(tempfile.mkdtemp(prefix='rf_test_'))
    workflows_dir = tmp / 'workflows'
    workflows_dir.mkdir()
    # Create a test workflow
    (workflows_dir / 'test-wf.yaml').write_text(
        "description: test workflow\n"
        "adversarial_check:\n  enabled: true\n  timeout_ms: 60000\n"
        "steps:\n"
        "  - id: step1\n    desc: first step\n    do: do something\n"
        "    input: none\n    output: result\n    check: verify result\n"
        "    on_pass: step2\n    on_fail: step1\n    max_fail_count: 3\n"
        "  - id: step2\n    desc: final step\n    do: final task\n"
        "    input: step1 output\n    output: done\n    check: final check\n"
        "    on_pass: done\n    on_fail: step2\n    max_fail_count: 5\n",
        encoding='utf-8'
    )
    # Create a sub-workflow
    (workflows_dir / 'sub-wf.yaml').write_text(
        "description: sub workflow\n"
        "steps:\n"
        "  - id: sub1\n    desc: sub step\n    do: sub task\n"
        "    input: none\n    output: sub result\n    check: sub check\n"
        "    on_pass: done\n    on_fail: sub1\n    max_fail_count: 2\n",
        encoding='utf-8'
    )
    return tmp


def teardown_test_env(tmp):
    shutil.rmtree(tmp, ignore_errors=True)


# ===== paths.py =====
def test_paths():
    print("\n--- paths.py ---")
    tmp = setup_test_env()
    try:
        # get_skill_dir should traverse up from a tool file
        fake_tool = tmp / 'tools' / 'rf-test' / 'run.py'
        fake_tool.parent.mkdir(parents=True)
        fake_tool.touch()
        skill_dir = get_skill_dir(str(fake_tool))
        test("get_skill_dir returns correct path", skill_dir == tmp, f"got {skill_dir}")

        test("get_workflows_dir", (tmp / 'workflows') == get_workflows_dir(tmp))
        test("get_state_file", (tmp / 'state.json') == get_state_file(tmp))
        test("get_stack_file", (tmp / 'state_stack.json') == get_stack_file(tmp))
        test("get_logs_dir", (tmp / 'logs') == get_logs_dir(tmp))
        test("get_step_records_file", (tmp / 'step_records.json') == get_step_records_file(tmp))
    finally:
        teardown_test_env(tmp)


# ===== state.py =====
def test_state():
    print("\n--- state.py ---")
    tmp = setup_test_env()
    try:
        # read_state when no file
        test("read_state returns None when no file", read_state(tmp) is None)

        # write and read state
        state = {
            'active': True,
            'workflow_name': 'test-wf',
            'current_step': 'step1',
            'current_phase': 'do',
            'fail_count': 0,
            'user_task': 'test task',
            'paused': False,
        }
        write_state(tmp, state)
        loaded = read_state(tmp)
        test("write_state + read_state roundtrip", loaded is not None and loaded['workflow_name'] == 'test-wf')

        # mark_completed
        mark_completed(tmp, state)
        loaded = read_state(tmp)
        test("mark_completed sets active=False", loaded['active'] is False)
        test("mark_completed sets completed_at", 'completed_at' in loaded)

        # mark_paused
        state['active'] = True
        state['paused'] = False
        write_state(tmp, state)
        mark_paused(tmp, state)
        loaded = read_state(tmp)
        test("mark_paused sets paused=True", loaded['paused'] is True)

        # state stack
        test("get_stack_depth initially 0", get_stack_depth(tmp) == 0)
        push_state(tmp, {'workflow_name': 'parent', 'current_step': 'p1'})
        test("get_stack_depth after push", get_stack_depth(tmp) == 1)
        push_state(tmp, {'workflow_name': 'child', 'current_step': 'c1'})
        test("get_stack_depth after 2nd push", get_stack_depth(tmp) == 2)

        popped = pop_state(tmp)
        test("pop_state returns last pushed", popped is not None and popped['workflow_name'] == 'child')
        test("get_stack_depth after pop", get_stack_depth(tmp) == 1)

        popped2 = pop_state(tmp)
        test("pop_state returns first pushed", popped2 is not None and popped2['workflow_name'] == 'parent')
        test("get_stack_depth after all pops", get_stack_depth(tmp) == 0)

        # pop when empty
        test("pop_state returns None when empty", pop_state(tmp) is None)

        # clear_state
        write_state(tmp, state)
        push_state(tmp, state)
        clear_state(tmp)
        test("clear_state removes state file", read_state(tmp) is None)
        test("clear_state clears stack", get_stack_depth(tmp) == 0)
    finally:
        teardown_test_env(tmp)


# ===== workflow.py =====
def test_workflow():
    print("\n--- workflow.py ---")
    tmp = setup_test_env()
    try:
        # list_workflows
        workflows = list_workflows(tmp)
        test("list_workflows finds workflows", len(workflows) >= 2)
        names = [w['name'] for w in workflows]
        test("list_workflows includes test-wf", 'test-wf' in names)
        test("list_workflows includes sub-wf", 'sub-wf' in names)

        # load_workflow
        wf = load_workflow(tmp, 'test-wf')
        test("load_workflow returns dict", wf is not None)
        test("load_workflow has steps", 'steps' in wf and len(wf['steps']) == 2)
        test("load_workflow has adversarial_check", 'adversarial_check' in wf)

        # load non-existent
        test("load_workflow returns None for missing", load_workflow(tmp, 'nonexistent') is None)

        # get_step
        step1 = get_step(wf, 'step1')
        test("get_step finds step1", step1 is not None and step1['id'] == 'step1')
        step2 = get_step(wf, 'step2')
        test("get_step finds step2", step2 is not None and step2['id'] == 'step2')
        test("get_step returns None for missing", get_step(wf, 'nonexistent') is None)

        # is_sub_workflow_step
        test("is_sub_workflow_step returns False for normal step", not is_sub_workflow_step(step1))
        sub_step = {'id': 'sub', 'workflow': 'sub-wf'}
        test("is_sub_workflow_step returns True for sub-workflow step", is_sub_workflow_step(sub_step))
    finally:
        teardown_test_env(tmp)


# ===== tags.py =====
def test_tags():
    print("\n--- tags.py ---")
    # done tag
    test("detect_done_tag True", detect_done_tag("work done\n<promise>done</promise>"))
    test("detect_done_tag True with spaces", detect_done_tag("<promise> done </promise>"))
    test("detect_done_tag True case insensitive", detect_done_tag("<Promise>DONE</Promise>"))
    test("detect_done_tag False when absent", not detect_done_tag("work done, no tag"))
    test("detect_done_tag False for partial match", not detect_done_tag("<promise>doing</promise>"))

    # check tag
    r1 = detect_check_tag("check passed\n<promise-check>true</promise-check>")
    test("detect_check_tag found=true, passed=true", r1['found'] and r1['passed'])

    r2 = detect_check_tag("check failed\n<promise-check>false</promise-check>")
    test("detect_check_tag found=true, passed=false", r2['found'] and not r2['passed'])

    r3 = detect_check_tag("no check tag here")
    test("detect_check_tag found=false when absent", not r3['found'])

    r4 = detect_check_tag("<promise-check> true </promise-check>")
    test("detect_check_tag handles spaces", r4['found'] and r4['passed'])

    r5 = detect_check_tag("<PROMISE-CHECK>FALSE</PROMISE-CHECK>")
    test("detect_check_tag case insensitive", r5['found'] and not r5['passed'])


# ===== logging.py =====
def test_logging():
    print("\n--- logging.py ---")
    tmp = setup_test_env()
    try:
        # log_event
        log_event(tmp, 'info', 'test_event', {'key': 'value'})
        log_file = tmp / 'logs' / 'execution.log'
        test("log_event creates log file", log_file.exists())
        content = log_file.read_text(encoding='utf-8').strip()
        entry = json.loads(content)
        test("log_event writes JSON", entry['event'] == 'test_event')
        test("log_event includes level", entry['level'] == 'info')

        # log_step_event
        log_step_event(tmp, 'step1', 'do', 'info', 'step_test', {'detail': 'x'})
        step_log = tmp / 'logs' / 'step-step1-do.log'
        test("log_step_event creates step log", step_log.exists())

        # convenience functions
        log_workflow_start(tmp, 'test-wf')
        log_workflow_end(tmp, 'test-wf')
        log_step_start(tmp, 'step1', 'do')
        log_done_detected(tmp, 'step1')
        log_check_result(tmp, 'step1', True)
        log_info(tmp, 'custom_event', {'data': 42})
        test("convenience logging functions don't crash", True)
    finally:
        teardown_test_env(tmp)


# ===== report.py =====
def test_report():
    print("\n--- report.py ---")
    tmp = setup_test_env()
    try:
        # create_step_record
        record = create_step_record('step1', 'do', 'passed', 0)
        test("create_step_record has stepId", record['stepId'] == 'step1')
        test("create_step_record has phase", record['phase'] == 'do')
        test("create_step_record has status", record['status'] == 'passed')

        record2 = create_step_record('step1', 'check', 'failed', 2, 'test failed')
        test("create_step_record with reason", record2['reason'] == 'test failed')

        # write and read step records
        write_step_records(tmp, [record, record2])
        loaded = read_step_records(tmp)
        test("write/read step records roundtrip", len(loaded) == 2)

        # append_step_record
        record3 = create_step_record('step2', 'do', 'passed', 0)
        append_step_record(tmp, record3)
        loaded = read_step_records(tmp)
        test("append_step_record adds record", len(loaded) == 3)

        # clear_step_records
        clear_step_records(tmp)
        loaded = read_step_records(tmp)
        test("clear_step_records empties records", len(loaded) == 0)

        # generate_completion_report
        append_step_record(tmp, record)
        report_path = generate_completion_report(tmp, 'test-wf')
        test("generate_completion_report creates file", report_path.exists())
        content = report_path.read_text(encoding='utf-8')
        test("completion report contains workflow name", 'test-wf' in content)
        test("completion report marks completed", '已完成' in content)

        # generate_cancel_report
        report_path = generate_cancel_report(
            tmp, 'test-wf',
            reason='user cancelled',
            current_step='step1',
            current_phase='do',
            fail_count=2
        )
        test("generate_cancel_report creates file", report_path.exists())
        content = report_path.read_text(encoding='utf-8')
        test("cancel report contains reason", 'user cancelled' in content)

        # generate_pause_report
        report_path = generate_pause_report(tmp, 'test-wf')
        test("generate_pause_report creates file", report_path.exists())
        content = report_path.read_text(encoding='utf-8')
        test("pause report marks paused", '已暂停' in content)

        # read_step_records when no file
        clear_step_records(tmp)
        (tmp / 'step_records.json').unlink(missing_ok=True)
        test("read_step_records returns [] when no file", read_step_records(tmp) == [])
    finally:
        teardown_test_env(tmp)


if __name__ == '__main__':
    print("=" * 60)
    print("rf_lib Unit Tests")
    print("=" * 60)

    test_paths()
    test_state()
    test_workflow()
    test_tags()
    test_logging()
    test_report()

    print("\n" + "=" * 60)
    total = PASS + FAIL
    print(f"Results: {PASS}/{total} passed, {FAIL}/{total} failed")
    if FAIL > 0:
        print("SOME TESTS FAILED!")
        sys.exit(1)
    else:
        print("ALL TESTS PASSED!")
    print("=" * 60)
