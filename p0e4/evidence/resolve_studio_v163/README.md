# V16.3 — Resolve Studio capability acceptance

Status: **INSTALLED_SYNTHETIC_CAPABILITIES_ACCEPTED_PRODUCTION_BLOCKED**.

Remote branch reconciled at 19d8da5. Installed Studio 21.1.0.17 verified through
Python and Lua. 74/74 offline suites passed; 483 historical manifest entries
matched. Acceptance and replay decoded to identical video and audio essences:
100 frames, 640x360, 25 fps; 192000 PCM samples/channel at 48 kHz. Container
SHA256 differs between runs; no byte-identical MOV claim. All renders stay local.

Exact initial render SHA256:
`6bbbfdbb482c5c187c6b5a55ad6b1b2d7b0c1fccae054b2d614d35ee8bdd9681`.

Cuts use exclusive source ends in this installed build. Native subtitles were
recovered by creating a subtitle track and explicitly setting the playhead; two
cues read back at [0,50) and [50,100), and the caption burn-in decoded and was
visually checked. Fusion composition export/import and whole-cue text emphasis
work. Effects Library MacroOperator paste, arbitrary Fairlight sample insertion,
waveform auto-sync on this fixture and character-span emphasis remain fail-closed.
These are bounded test results, not claims that Resolve lacks the features.

General production execution remains closed. No Nitin audio-source binding was
inferred; no authenticated Gemini or Claude result was fabricated. The next real
finishing step needs Nitin's exact audio-source binding and operation coverage.
Production/publication remain false; First Real Poster remains PAUSED_BY_NITIN.

## Capability matrix

| Capability | Classification | Evidence |
|---|---|---|
| installed_version_edition | API_SCRIPTABLE | INSTALLATION.json |
| resolve_api_connectivity | API_SCRIPTABLE | INSTALLATION.json |
| python_external_scripting | API_SCRIPTABLE | INSTALLATION.json |
| lua_external_scripting | API_SCRIPTABLE | INSTALLATION.json |
| project_creation | API_SCRIPTABLE | LOCAL_ACCEPTANCE.json |
| synthetic_media_import | API_SCRIPTABLE | LOCAL_ACCEPTANCE.json |
| timeline_creation | API_SCRIPTABLE | LOCAL_ACCEPTANCE.json |
| cuts | API_SCRIPTABLE | LOCAL_ACCEPTANCE.json |
| static_transform_reframe | API_SCRIPTABLE | LOCAL_ACCEPTANCE.json |
| fusion_access_scriptability | FUSION_SCRIPTABLE | LOCAL_ACCEPTANCE.json |
| zoom_push_in_keyframes | FUSION_SCRIPTABLE | LOCAL_ACCEPTANCE.json |
| deterministic_rotational_shake | FUSION_SCRIPTABLE | LOCAL_ACCEPTANCE.json |
| glow | FUSION_SCRIPTABLE | LOCAL_ACCEPTANCE.json |
| text_title | FUSION_SCRIPTABLE | LOCAL_ACCEPTANCE.json |
| whole_cue_lyric_emphasis | FUSION_SCRIPTABLE | LOCAL_ACCEPTANCE.json |
| reusable_fusion_composition_templates | FUSION_SCRIPTABLE | LOCAL_ACCEPTANCE.json |
| native_titles | API_SCRIPTABLE | CAPTIONS_ACCEPTANCE.json |
| native_subtitles_captions | API_SCRIPTABLE | CAPTIONS_ACCEPTANCE.json |
| fusion_effects_library_macro_installation | UNSUPPORTED_FAIL_CLOSED | MACRO_FAILED_PROBE.json |
| per_character_lyric_emphasis | UNSUPPORTED_FAIL_CLOSED | LOCAL_ACCEPTANCE.json |
| audio_import_frame_alignment | API_SCRIPTABLE | LOCAL_ACCEPTANCE.json |
| fairlight_callable_surface | API_SCRIPTABLE | LOCAL_ACCEPTANCE.json |
| fairlight_sample_offset_insertion | UNSUPPORTED_FAIL_CLOSED | SUPPLEMENTAL_PROBE.json |
| waveform_auto_sync | UNSUPPORTED_FAIL_CLOSED | SUBTITLE_SYNC_PROBE.json |
| semantic_audio_sync_lip_sync | EXTERNAL_INTELLIGENCE_REQUIRED | READBACK_REPLAY.json |
| lyric_transcription_alignment | EXTERNAL_INTELLIGENCE_REQUIRED | READBACK_REPLAY.json |
| creative_cut_reframe_selection | EXTERNAL_INTELLIGENCE_REQUIRED | READBACK_REPLAY.json |
| gemini_output_qc | EXTERNAL_INTELLIGENCE_REQUIRED | READBACK_REPLAY.json |
| render_queue_private_export | API_SCRIPTABLE | LOCAL_ACCEPTANCE.json |
| output_sha_readback | API_SCRIPTABLE | READBACK_REPLAY.json |

Private project exports, rendered media, and sampled frames are intentionally outside Git.
The original Untitled Project was restored. Disposable projects are retained locally
for diagnosis. Acceptance/replay render jobs were removed.
