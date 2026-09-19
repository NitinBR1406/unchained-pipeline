"""Pure shadow projection into observed legacy headers; has no Sheets client.

Sidecar preserves the full canonical package and edit plan. It is not consumed by
legacy Make automatically. A required unmapped capability always blocks dispatch.
"""
from copy import deepcopy
from integration.contracts import canonical,digest,require
from .validator import validate


def shadow(data,creative,field_map,snapshot,resolver,required_fields=('caption','hashtags','title')):
    validate(data,creative,resolver)
    require(field_map['schema_version']==1 and type(field_map['schema_version']) is int,'map version')
    require(field_map['snapshot_sha256']==digest(canonical(snapshot)),'snapshot drift')
    sheet=next(s for s in snapshot['sheets'] if s['properties']['title']=='Captions_Publishing')
    headers=sheet['headers'];require(len(headers)==len(set(headers)) and all(headers),'invalid headers')
    identities=set()
    for m in field_map['fields']:
        identity=(m['platform'],m['canonical_field'])
        require(identity not in identities,'duplicate mapping');identities.add(identity)
        require(bool(m['evidence_refs']),'mapping without evidence')
        for ref in m['evidence_refs']:require(digest(resolver(ref['uri']))==ref['sha256'],'mapping evidence drift')
    rows=[]
    for p in data['PLATFORM_PACKAGES']:
        mappings=[m for m in field_map['fields'] if m['platform']==p['platform'] and m['status']=='VERIFIED']
        available={m['canonical_field'] for m in mappings}
        require(set(required_fields)<=available,'REQUIRED_UNMAPPED_FIELDS')
        cells={}
        for m in mappings:
            require(m['spreadsheet_id']==snapshot['spreadsheet_id'] and m['tab']==sheet['properties']['title'],'target mismatch')
            require(m['sheet_id']==sheet['properties']['sheetId'],'sheet ID mismatch')
            require(0<=m['column_index']<len(headers) and headers[m['column_index']]==m['header'],'header drift')
            require(bool(m['evidence_refs']),'mapping without evidence')
            for ref in m['evidence_refs']:require(digest(resolver(ref['uri']))==ref['sha256'],'mapping evidence drift')
            value=deepcopy(p[m['canonical_field']])
            if m['transformation']=='join_space':
                require(type(value) is list and all(type(x) is str and ' ' not in x for x in value),'lossy hashtags')
                value=' '.join(value)
            else:require(m['transformation']=='identity','unsupported transformation')
            require(m['header'] not in cells,'conflicting column mapping')
            cells[m['header']]=value
        # Every dispatch flag is FALSE in the shadow. No live New/Ready status emitted.
        controls={h:'FALSE' for h in headers if h.startswith('publish_to_')}
        rows.append(dict(package_id=p['package_id'],platform=p['platform'],cells=cells,controls=controls,
                         cells_by_index={str(headers.index(k)):v for k,v in dict(cells,**controls).items()},value_input_option='RAW'))
    return dict(schema='CLAUDE_CANONICAL_SHADOW',schema_version=1,status='SHADOW_ONLY_NOT_DISPATCHABLE',
                canonical_sha256=digest(canonical(data)),map_sha256=digest(canonical(field_map)),rows=rows,
                sidecar=deepcopy(data),creative_package=deepcopy(creative),external_writes=0)


def readback(shadow_result,field_map,snapshot,resolver):
    # Rebuild expected projection from retained canonical bytes, not lossy reverse guesses.
    source=shadow_result['sidecar'];creative=shadow_result['creative_package']
    require(shadow_result==shadow(source,creative,field_map,snapshot,resolver),'SEMANTIC_DRIFT')
    return deepcopy(source)


def dispatch(*args,**kwargs):
    raise ValueError('LIVE_CUTOVER_NOT_AUTHORIZED: shadow-only adapter')
