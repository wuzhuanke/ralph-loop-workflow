#!/usr/bin/env python3
"""
rf-detect tool - Detect workflow tags in text
"""
import json
import sys
import re
from pathlib import Path

# Tag patterns
DONE_TAG = re.compile(r'<promise>\s*done\s*</promise>', re.IGNORECASE)
CHECK_TAG = re.compile(r'<promise-check>\s*(true|false)\s*</promise-check>', re.IGNORECASE)

def detect_done_tag(text: str) -> bool:
    """Detect if done tag is present in text"""
    if not text:
        return False

    trimmed = text.strip()

    # Check if done tag is on the last line (most reliable)
    lines = trimmed.split("\n")
    last_line = lines[-1].strip()
    if DONE_TAG.search(last_line):
        return True

    # Also check if it's at the end of the text (within last 100 chars)
    last_part = trimmed[-100:] if len(trimmed) > 100 else trimmed
    return bool(DONE_TAG.search(last_part))

def detect_check_tag(text: str) -> dict:
    """Detect check tag and return result"""
    if not text:
        return {"found": False, "passed": None, "reason": ""}

    match = CHECK_TAG.search(text)
    if not match:
        return {"found": False, "passed": None, "reason": ""}

    passed = match.group(1).lower() == "true"

    # Extract reason (text before the tag)
    lines = text.strip().split("\n")
    reason_lines = []
    for line in lines:
        if CHECK_TAG.search(line):
            break
        reason_lines.append(line)

    reason = "\n".join(reason_lines).strip()
    # Truncate if too long
    if len(reason) > 5000:
        reason = reason[:5000] + "..."

    return {
        "found": True,
        "passed": passed,
        "reason": reason
    }

def main():
    # Get paths
    script_dir = Path(__file__).parent
    tools_dir = script_dir.parent
    skill_dir = tools_dir.parent
    state_file = skill_dir / 'state.json'

    # Read input from stdin
    input_data = json.load(sys.stdin)
    text = input_data.get('text', '')

    # Detect tags
    done_detected = detect_done_tag(text)
    check_result = detect_check_tag(text)

    # Build response
    result = {
        "done_detected": done_detected,
        "check_result": check_result
    }

    # If check tag found and we have an active workflow, update state
    if check_result["found"] and state_file.exists():
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)

            if state.get('active', False):
                if check_result["passed"]:
                    # Check passed - could update to next step
                    result["suggestion"] = "Check passed. Consider advancing to next step."
                else:
                    # Check failed - increment fail count
                    fail_count = state.get('fail_count', 0) + 1
                    result["suggestion"] = f"Check failed (attempt {fail_count}). Consider retry with failure context."
                    result["failure_reason"] = check_result["reason"]
        except:
            pass

    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
