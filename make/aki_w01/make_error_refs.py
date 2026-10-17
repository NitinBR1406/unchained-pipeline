"""Bind error references in Make error handlers to the failing module.

Runtime finding T2 v3 (2026-10-14, scenario 9975668): inside an error-handler route the bare
{{error.type}}, {{error.name}} and {{error.message}} are EMPTY, while {{<failed module id>.error.type}}
and {{<id>.error.message}} carry the values. Every handler expression is therefore rewritten to
reference the module whose onerror route it sits in. (.statusCode and toString(<id>.error) follow the
same pattern but were not separately runtime-verified. Not covered: a bare {{error}} or other fields such as error.code.)
"""
import re
BARE = re.compile(r'(?<![\w.])error(?=\.(?:type|name|message|statusCode)\b|\))')


def _rewrite(x, mid):
    if isinstance(x, str):
        return BARE.sub('%d.error' % mid, x)
    if isinstance(x, dict):
        return {k: (v if k == 'onerror' else _rewrite(v, mid)) for k, v in x.items()}
    if isinstance(x, list):
        return [_rewrite(v, mid) for v in x]
    return x


def bind_error_refs(flow):
    for m in flow:
        if m.get('onerror'):
            m['onerror'] = [_rewrite(h, m['id']) for h in m['onerror']]
            bind_error_refs(m['onerror'])
        for r in m.get('routes') or []:
            bind_error_refs(r['flow'])
    return flow


def bare_error_refs(flow):
    """All remaining bare error.* references (should be none after bind_error_refs)."""
    import json
    return BARE.findall(json.dumps(flow))
