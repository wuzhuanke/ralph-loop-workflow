"""Report generation for ralph-flow tools."""
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime


def format_duration(start: str, end: str) -> str:
    """Format duration between two ISO timestamps."""
    try:
        start_ts = datetime.fromisoformat(start).timestamp()
        end_ts = datetime.fromisoformat(end).timestamp()
        duration_s = int(end_ts - start_ts)
        minutes = duration_s // 60
        seconds = duration_s % 60
        if minutes > 0:
            return f"{minutes}分钟{seconds}秒"
        return f"{seconds}秒"
    except Exception:
        return "未知"


def create_step_record(
    step_id: str,
    phase: str,
    status: str,
    fail_count: int,
    reason: Optional[str] = None,
    start_time: Optional[str] = None
) -> Dict[str, Any]:
    """Create a step execution record."""
    now = datetime.now().isoformat()
    return {
        'stepId': step_id,
        'phase': phase,
        'status': status,
        'failCount': fail_count,
        'startTime': start_time or now,
        'endTime': now,
        'reason': reason,
    }


def read_step_records(skill_dir: Path) -> List[Dict[str, Any]]:
    """Read step records from file."""
    from rf_lib.paths import get_step_records_file
    records_file = get_step_records_file(skill_dir)
    if not records_file.exists():
        return []
    try:
        with open(records_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def write_step_records(skill_dir: Path, records: List[Dict[str, Any]]) -> None:
    """Write step records to file."""
    from rf_lib.paths import get_step_records_file
    records_file = get_step_records_file(skill_dir)
    with open(records_file, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def append_step_record(skill_dir: Path, record: Dict[str, Any]) -> None:
    """Append a step record to the records file."""
    records = read_step_records(skill_dir)
    records.append(record)
    write_step_records(skill_dir, records)


def clear_step_records(skill_dir: Path) -> None:
    """Remove step records file."""
    from rf_lib.paths import get_step_records_file
    records_file = get_step_records_file(skill_dir)
    if records_file.exists():
        records_file.unlink()


def _generate_report_markdown(
    workflow_name: str,
    status: str,
    steps: List[Dict[str, Any]]
) -> str:
    """Generate Markdown report content."""
    total_failures = sum(r.get('failCount', 0) for r in steps)
    start_time = steps[0]['startTime'] if steps else datetime.now().isoformat()
    end_time = steps[-1].get('endTime') or datetime.now().isoformat() if steps else datetime.now().isoformat()

    status_text = {
        'completed': '已完成',
        'cancelled': '已取消',
        'paused': '已暂停',
    }.get(status, status)

    lines = [
        "# 工作流执行报告",
        "",
        "## 执行摘要",
        "",
        f"- **工作流**: {workflow_name}",
        f"- **状态**: {status_text}",
        f"- **总步骤数**: {len(steps)}",
        f"- **失败次数**: {total_failures}",
        f"- **总耗时**: {format_duration(start_time, end_time)}",
        "",
        "## 步骤执行情况",
        "",
    ]

    for i, record in enumerate(steps):
        status_icon = "✓" if record['status'] == 'passed' else "✗"
        lines.append(f"### {i + 1}. {record['stepId']} ({record['phase']}) {status_icon}")
        lines.append(f"- 状态：{'通过' if record['status'] == 'passed' else '失败'}")
        if record.get('failCount', 0) > 0:
            lines.append(f"- 失败次数：{record['failCount']}")
        if record.get('reason'):
            label = '通过原因' if record['status'] == 'passed' else '失败原因'
            lines.append(f"- {label}：{record['reason']}")
        if record.get('startTime') and record.get('endTime'):
            lines.append(f"- 耗时：{format_duration(record['startTime'], record['endTime'])}")
        lines.append("")

    return '\n'.join(lines)


def generate_report(
    skill_dir: Path,
    workflow_name: str,
    status: str,
    steps: Optional[List[Dict[str, Any]]] = None
) -> Path:
    """Generate a report file and return its path."""
    from rf_lib.paths import get_logs_dir
    logs_dir = get_logs_dir(skill_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)

    if steps is None:
        steps = read_step_records(skill_dir)

    markdown = _generate_report_markdown(workflow_name, status, steps)
    report_file = logs_dir / 'final-report.md'
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(markdown)

    return report_file


def generate_completion_report(skill_dir: Path, workflow_name: str, steps: Optional[List[Dict[str, Any]]] = None) -> Path:
    """Generate a completion report."""
    from rf_lib.paths import get_logs_dir
    logs_dir = get_logs_dir(skill_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)

    if steps is None:
        steps = read_step_records(skill_dir)

    markdown = _generate_report_markdown(workflow_name, 'completed', steps)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = logs_dir / f'report_{timestamp}.md'
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(markdown)

    return report_file


def generate_cancel_report(
    skill_dir: Path,
    workflow_name: str,
    reason: str = '',
    current_step: str = '',
    current_phase: str = '',
    fail_count: int = 0,
    steps: Optional[List[Dict[str, Any]]] = None
) -> Path:
    """Generate a cancellation report with extra context."""
    from rf_lib.paths import get_logs_dir
    logs_dir = get_logs_dir(skill_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)

    if steps is None:
        steps = read_step_records(skill_dir)

    # Build cancellation-specific markdown
    markdown = _generate_report_markdown(workflow_name, 'cancelled', steps)
    extra = [
        "",
        "## 取消详情",
        "",
        f"- **取消原因**: {reason}",
        f"- **取消时步骤**: {current_step}",
        f"- **取消时阶段**: {current_phase}",
        f"- **累计失败次数**: {fail_count}",
    ]
    markdown += '\n'.join(extra)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = logs_dir / f'cancel_report_{timestamp}.md'
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(markdown)

    return report_file


def generate_pause_report(skill_dir: Path, workflow_name: str, steps: Optional[List[Dict[str, Any]]] = None) -> Path:
    """Generate a pause report."""
    from rf_lib.paths import get_logs_dir
    logs_dir = get_logs_dir(skill_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)

    if steps is None:
        steps = read_step_records(skill_dir)

    markdown = _generate_report_markdown(workflow_name, 'paused', steps)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = logs_dir / f'pause_report_{timestamp}.md'
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(markdown)

    return report_file
