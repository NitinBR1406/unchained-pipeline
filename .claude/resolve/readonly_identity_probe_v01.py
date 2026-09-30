# UNCHAINED NITIN - pinned read-only Resolve identity probe V01.
# Only Get*/Is* calls. No setters, no page switch, no project load, no render.
pm = resolve.GetProjectManager()
p = pm.GetCurrentProject() if pm else None
tl = p.GetCurrentTimeline() if p else None
result = {
    "product": resolve.GetProductName(),
    "version": resolve.GetVersionString(),
    "current_page": resolve.GetCurrentPage(),
    "project_name": p.GetName() if p else None,
    "project_unique_id": p.GetUniqueId() if p else None,
    "project_timeline_count": p.GetTimelineCount() if p else None,
    "rendering_in_progress": p.IsRenderingInProgress() if p else None,
    "timeline_name": tl.GetName() if tl else None,
    "timeline_unique_id": tl.GetUniqueId() if tl else None,
    "timeline_start_frame": tl.GetStartFrame() if tl else None,
    "timeline_end_frame": tl.GetEndFrame() if tl else None,
    "timeline_frame_rate": tl.GetSetting("timelineFrameRate") if tl else None,
    "timeline_resolution": [tl.GetSetting("timelineResolutionWidth"), tl.GetSetting("timelineResolutionHeight")] if tl else None,
}
