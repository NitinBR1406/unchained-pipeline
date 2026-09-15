"""Dependency-aware backlog. WAITING_FOR_NITIN on one task never blocks independent READY tasks."""
LIFECYCLE={"READY","CLAIMED","RUNNING","VERIFYING","COMPLETED","BLOCKED","WAITING_FOR_NITIN","FAILED"}
TERMINAL={"COMPLETED","FAILED"}
def ready_tasks(tasks):
    """tasks: list of dicts with task_id, status, dependencies[]. Returns independently-executable READY tasks."""
    done={t["task_id"] for t in tasks if t.get("status")=="COMPLETED"}
    out=[]
    for t in tasks:
        if t.get("status")!="READY": continue
        if all(dep in done for dep in t.get("dependencies",[])): out.append(t)
    return out
def summary(tasks):
    c={k:0 for k in ("ready","running","blocked","waiting_for_nitin","completed","failed","claimed","verifying")}
    m={"READY":"ready","RUNNING":"running","BLOCKED":"blocked","WAITING_FOR_NITIN":"waiting_for_nitin",
       "COMPLETED":"completed","FAILED":"failed","CLAIMED":"claimed","VERIFYING":"verifying"}
    for t in tasks:
        k=m.get(t.get("status"))
        if k: c[k]+=1
    return c
