"""Explicit Gemini V1 bridge. Editorial fields must be supplied; never invented."""
from copy import deepcopy
from integration.contracts import require,canonical,digest,validate as validate_creative
from .validator import SCHEMA,validate


def assemble(creative,records,evidence_refs,created_at,resolver):
    validate_creative(creative)
    table_names={k for k,v in SCHEMA['properties'].items() if v.get('type')=='array' and k!='evidence_refs'}
    require(set(records)==table_names,'missing/unknown canonical tables')
    d=dict(schema='UNCHAINED_FACTORY_CANONICAL',schema_version=1,mode='SHADOW_ONLY',
           content_id=creative['content_id'],created_at=created_at,source_package_sha256=digest(canonical(creative)),
           evidence_refs=deepcopy(evidence_refs),governance=dict(production_deployment_authorized=False,
           publication_authorized=False,first_real_poster='PAUSED_BY_NITIN',minimum_performance_fraction='4/5'),**deepcopy(records))
    validate(d,creative,resolver)
    return d
