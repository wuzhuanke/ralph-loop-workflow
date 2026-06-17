#!/usr/bin/env python3
"""
rf-list tool - List available workflows
"""
import json
import sys
from pathlib import Path

def main():
    # Get paths
    script_dir = Path(__file__).parent  # tools/rf-list
    tools_dir = script_dir.parent       # tools
    skill_dir = tools_dir.parent        # ralpha-loop-workflow
    workflows_dir = skill_dir / 'workflows'

    # Check if workflows directory exists
    if not workflows_dir.exists():
        print(json.dumps({
            'workflows': [],
            'message': f'No workflows directory found at {workflows_dir}'
        }, ensure_ascii=False))
        return

    # List workflow files
    workflows = []
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
            workflows.append({'name': name, 'description': desc})

    if not workflows:
        print(json.dumps({
            'workflows': [],
            'message': f'No workflow files found in {workflows_dir}'
        }, ensure_ascii=False))
    else:
        print(json.dumps({
            'workflows': workflows
        }, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
