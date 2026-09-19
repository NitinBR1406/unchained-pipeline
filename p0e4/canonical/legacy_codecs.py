"""Pure codecs for evidenced legacy transport, never a live write adapter.

Make N2 uses space-delimited hashtags/comma-delimited keywords. N7 explicitly
parses Amsterdam wall time. Ambiguous/nonexistent DST times fail closed.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from integration.contracts import require
FORMAT='%Y-%m-%d %H:%M:%S'
ZONE=ZoneInfo('Europe/Amsterdam')


def encode_tokens(values, kind):
    require(kind in ('hashtags','keywords'),'unknown token kind')
    require(type(values) is list and bool(values),'nonempty tokens required')
    separator=' ' if kind=='hashtags' else ', '
    for v in values:
        require(type(v) is str and bool(v) and v==v.strip(),'invalid token')
        require((',' not in v if kind=='keywords' else separator not in v) and not any(c in v for c in '\r\n\t'),'lossy delimiter')
        if kind=='hashtags':require(v.startswith('#') and len(v)>1,'invalid hashtag')
    return separator.join(values)


def decode_tokens(value,kind):
    require(type(value) is str,'token wire type')
    require(kind in ('hashtags','keywords'),'unknown token kind')
    values=value.split(' ' if kind=='hashtags' else ', ')
    require(encode_tokens(values,kind)==value,'noncanonical tokens')
    return values


def decode_schedule(value):
    require(type(value) is str,'schedule wire type')
    wall=datetime.strptime(value,FORMAT)
    require(wall.strftime(FORMAT)==value,'noncanonical schedule')
    candidates=set()
    for fold in (0,1):
        local=wall.replace(tzinfo=ZONE,fold=fold)
        utc=local.astimezone(timezone.utc)
        if utc.astimezone(ZONE).replace(tzinfo=None)==wall:candidates.add(utc)
    require(len(candidates)==1,'ambiguous or nonexistent legacy schedule')
    return next(iter(candidates)).isoformat().replace('+00:00','Z')


def encode_schedule(value):
    require(type(value) is str,'canonical schedule type')
    dt=datetime.fromisoformat(value.replace('Z','+00:00'))
    require(dt.tzinfo is not None and dt.utcoffset() is not None,'schedule offset required')
    require(dt.microsecond==0,'legacy schedule loses subsecond precision')
    result=dt.astimezone(ZONE).strftime(FORMAT)
    require(datetime.fromisoformat(decode_schedule(result).replace('Z','+00:00'))==dt,'schedule drift')
    return result
