local r=bmd.scriptapp('Resolve'); local p=r:GetProjectManager():GetCurrentProject();assert(p:GetName()=='UNCHAINED_V163_SYNTHETIC_20260923');local t=p:GetCurrentTimeline()
r:OpenPage('fusion');t:SetCurrentTimecode('01:00:02:10')
local c=t:GetItemListInTrack('video',1)[2]:GetFusionCompByIndex(1)
local settings=bmd.readfile(arg[1]);dump(settings)
print('paste',c:Paste(settings))
print('paste string',c:Paste(io.open(arg[1]):read('*all')))
for _,tool in pairs(c:GetToolList(false)) do print(tool:GetAttrs().TOOLS_Name,tool:GetAttrs().TOOLS_RegID) end
