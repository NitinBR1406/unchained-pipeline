"""Additional unattended gate: deny every tool except the two existing read tools.

This supplements, never edits, the V02 project permission configuration.
"""
import hashlib
import json
import sys

PIN = '22cf949c0bd2b1fa657c542b5a9f3de057a39f444ceca85b3a970f6243ed4bf2'


def decide(event):
    name = event.get('tool_name')
    args = event.get('tool_input')
    if name == 'mcp__davinci_resolve__get_resolve_status' and args == {}:
        return 'allow'
    if name == 'mcp__davinci_resolve__run_script' and isinstance(args, dict) and set(args) == {'script'}:
        script = args['script']
        if isinstance(script, str) and hashlib.sha256((script.rstrip() + '\n').encode()).hexdigest() == PIN:
            return 'allow'
    return 'deny'


if __name__ == '__main__':
    try:
        decision = decide(json.load(sys.stdin))
    except Exception:
        decision = 'deny'
    print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse',
          'permissionDecision': decision, 'permissionDecisionReason': 'Bounded unattended read-only policy'}}))
