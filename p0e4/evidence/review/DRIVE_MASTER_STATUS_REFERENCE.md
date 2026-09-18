# AKI — Master Status Record (Aakhri Ishq)
_Plaats in: Unchained Nitin — Master / Campaigns / Aakhri-Ishq / 06_Analytics. Bijgewerkt 2026-09-05._

| Veld | Waarde |
|---|---|
| Campaign_ID | AKI |
| Song | Aakhri Ishq (Dhurandhar: The Revenge, cover) |
| Current_Source | AKI_SOURCE_0902_V01.mov (Drive `1Uk6Ru7wtU1Y3aCeOdYQwPhuTojHzDgN6`) |
| Current_Review_Version | **AKI_CLEANBASE_FX_V02.mp4** |
| Shared_Review_File_Status | AVAILABLE |
| AKI_SHARED_REVIEW_ASSET | READY |
| Nitin_Video_Approval | NOT_APPROVED |
| Branding_Status | CLEAN_BASE_READY (geen branding op dit asset) |
| Gemini_Review_Status | READY (V02 correction pass toegepast) |
| ChatGPT_Review_Status | READY |
| Claude_Dispatch_Status | BLOCKED |
| Publish_Status | NOT_PUBLISHED |
| Current_Blocker | AI_AND_NITIN_REVIEW |
| Last_Updated | 2026-09-05 |

## V02 — huidige review-versie
- Bestand: **AKI_CLEANBASE_FX_V02.mp4** · Drive ID `17VVNlP3n5numYZN3yj0P3ELLAKuPOaVD` · 152.266.942 bytes · ~214.6s
- Locatie: `Campaigns/Aakhri-Ishq/01_CapCut-Out/`
- GCS: `clips/cc2ab060a11640e0823a6f894055a624.mp4`
- Gerenderd door media-service **v13-audiofull**. Cues: `AKI_SMART_CUES_V02.json`.
- Bekijken: https://drive.google.com/file/d/17VVNlP3n5numYZN3yj0P3ELLAKuPOaVD/view

## Gemini V02-correcties (toegepast + geverifieerd)
- Stabiliteitsvensters GEEN beweging: 1:00.0–1:06.5 en 1:58.5–2:04.0.
- Max 2 witte flashes (40.519s, 184.517s), elk ≤2 frames (~68ms), directe decay.
- Micro-zoom 2:49–2:56: vloeiende ramp, piek op 2:56 + ease-out (geen abrupte reset).
- Primaire impact-cues behouden (0:41–0:46.5, 1:42–1:52, 3:01.5–3:07).
- **Audio byte-identiek aan V01** (v13 `-c:a copy`, volledig). Bewezen md5 `ae4e68cd38f873f49a2b73bd48b19bfe` — gelijk op de echte bestanden.
- Kleur / EQ / sequence ongewijzigd.

## Historie / bewaard
- V01: AKI_CLEANBASE_FX_V01.mp4 (Drive `1l0nhUpA21xfWPm8B14eWDjBntILjoaR4`, GCS `c95ba33269134d66a6a23264f4402c9f.mp4`). Blijft bestaan.
- Foutieve eerste V02 (laatste AAC-frame ~21ms afgekapt door v12) → prullenbak.

## Wat dit asset NIET is
NOT branded · NOT publish-ready · NOT in 04_Publish-Ready (gereserveerd voor NITIN_VIDEO_APPROVAL=APPROVED) · geen dispatch.

## Branding-correctie (voor de CapCut-stage — NIET op deze clean base)
- Geen aparte intro-lockup; 0:00.0–0:00.8 pure performance.
- ~0:00.8 korte in-performance titel: AAKHRI ISHQ (kleiner: UNCHAINED NITIN).
- Subtiel UN-watermerk later; korte outro ≤2s zonder socials.

