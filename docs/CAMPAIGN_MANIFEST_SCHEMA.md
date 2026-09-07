# Campaign Manifest Schema

Canonical format: `campaign.json` (YAML also loadable if PyYAML is installed). Generic across
covers/originals — no song-specific values are baked into pipeline logic.

## Required fields
- `campaign_id` (string, unique, folder-safe)
- `artist`, `song_title`, `release_type` ("cover" | "original")
- `source_master` (filename / reference of the immutable performance master)
- `duration` (seconds, float), `aspect_ratio` ("9:16"), `fps` (int)
- `presentation_preset` ("MOTION_A_PREMIUM_RESTRAINED" | "MOTION_B_PREMIUM_ROCK")
- `brand_profile` ("UNCHAINED_NITIN_BRAND_PROFILE_V1")
- `platform_targets` (list)

## Recommended fields
- `width`, `height` (default 1080×1920)
- `frozen_master` (path to the frozen Edit JSON), `production_master_name`
- `lyric_master`, `caption_schedule`, `motion_cues`, `song_structure`
- `intro_enabled`, `outro_enabled`
- `rights`: `{ status: RIGHTS_UNKNOWN|RIGHTS_REVIEW|RIGHTS_PASS|RIGHTS_HOLD, composition_publisher,
  backing_master_origin, content_id_expectation, note }`
- `release_status`

## Notes
- Approvals, state, registry, audit and reports live in an isolated `state/` dir next to the manifest;
  the manifest itself is config only.
- `presentation_preset` selects motion; MOTION_B is never auto-selected.
- See `campaigns/aakhri-ishq/campaign.json` for a complete example.
