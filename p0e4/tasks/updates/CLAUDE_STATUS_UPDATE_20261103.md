# Statusupdate Claude Code → ChatGPT — 03-11-2026

Type: statusupdate. **Geen taak.** Dit bestand staat bewust niet in `inbox/` en start geen runner.
Afzender: Claude Code (lokale sessie, op verzoek van Nitin).
Gates ongewijzigd: `PRODUCTION_DEPLOYMENT_AUTHORIZED = FALSE` · `PUBLICATION_AUTHORIZED = FALSE` (behalve Nitins per-post-akkoorden voor de AKI-campagne) · `FIRST_REAL_POSTER = PAUSED_BY_NITIN`.
Er staan geen tokens, ondertekende media-URL's of andere geheimen in dit bestand.

## 1. AKI-campagne: publicaties

### D10 middag — D10-S3 (foto), ma 02-11 12:00
- P2 (9974134) eenmaal handmatig gestart om 11:01Z (draaiboek D06–D11, besluit Nitin 28-10 en 02-11): SUCCESS.
- Instagram-feed PUBLISHED: 18097857779134914, https://www.instagram.com/p/DfPJt0qladZ/. Staging opgeruimd (404).
- Facebook-pagina PUBLISHED: 839373332878305_1776795157778857.
- Privé-FB: geplaatst op 02-11 rond 12:25.
- TikTok-foto: blijft `BLOCKED`; Nitin plaatst die handmatig. Status: nog niet geplaatst.
  Let op: de goedgekeurde tekst zegt "Chapter VII drops tonight"; bij later plaatsen klopt dat woord niet meer. Nitin is hierop gewezen.

### D10 avond — D10-V07 (Chapter VII · The Storm), ma 02-11 19:00
| Kanaal | Resultaat |
|---|---|
| Instagram Reels | PUBLISHED 18:01Z — https://www.instagram.com/reel/DfP5wFQktNa/ |
| Facebook-pagina | PUBLISHED — reel 1652049099998721 |
| YouTube Shorts | PUBLISHED — XoLGUpuStX4 |
| TikTok | `DRAFT_IN_TIKTOK_INBOX`; Nitin publiceert handmatig met de goedgekeurde caption |

- Runs: P3 (9975129) SUCCESS; P2 (9974134) 18:01:01Z–18:02:34Z SUCCESS.
- IG-staging opgeruimd: object `aki-ig-staging/<asset_sha256>.mp4`, generation 1793615495842755 verwijderd, controle gaf 404.
- Privé-FB (facebook.com/nitin.ramdaras.3): pagina-reel openbaar gedeeld met de Nederlandse tekst; identiteit vooraf gecontroleerd via facebook.com/me.
- Gelogd in de lokale campagnelogs (PUBLICATIELOG, PAKKET_D05_D11_REVIEW, STAGING_LOG).

### D11 — D11-V08 (Chapter VIII · The Voice), di 03-11 19:00
- Records `READY`, caption-versie `v2-approved-nitin-2026-10-28`.
- **Risico:** de geplande headless IG-staging (12:00) werd eerder geblokkeerd. Als de staging niet gelukt is, slaat P2 Instagram over; FB en YT gaan door. Interactieve staging alleen op Nitins verzoek.

## 2. TikTok-onderzoek (02-11) — voorstel, wacht op Nitin

Gemeten in TikTok Studio:
- AKI-posts D01–D09: 247–382 views per post. 85–95% van het verkeer komt uit "Voor jou".
- Chapter VI: gemiddelde kijktijd 2,9 s van 22 s; 0,8% volledig bekeken; kijkers haken af op 0:01.
- Laatste 7 dagen: 0 keer gedeeld, 0 reacties.
- Kijkers: 90% NL, 91% niet-volgers, 63% 35+.
- Gecorrigeerd: de video's beginnen níet stil of met een titelkaart (zang en gezicht vanaf 0:00, ca. −11 dB).

Waarschijnlijke oorzaken:
- het eerste beeld is elke dag hetzelfde;
- geen hook-tekst in seconde 0;
- niet-vindbare hashtags;
- lengte 22–29 s bij ~3 s kijktijd;
- wisselende posttijd.

Voorstel in twee fasen:
- **Fase 1:** alleen TikTok, vanaf D11. Hook-caption, vindbare hashtags (`#hindisong #bollywoodcover #hindicover #suriname #hindustaans #AakhriIshq`), tekst in beeld op seconde 0, vaste posttijd 19:00, actief in de eerste 30 minuten, cover-frame op een hoge noot. Credits blijven.
- **Fase 2:** een eigen TikTok-snede van 8–12 s uit bestaand materiaal. Alleen na apart akkoord en een aparte bouwtaak.
- **Meten:** na 72 uur, tegen de baseline van ~300 views en ~3 s.

**Besluit Nitin: open.** De goedgekeurde captions zijn niet gewijzigd. Wijkt Nitin af, dan geldt dat alleen voor TikTok en vraagt het zijn expliciete keuze.

## 3. Opname- en lichtadvies (03-11) — alleen advies, niets gebouwd

- **Lichtplan:** vijf lichtopstellingen voor de vaste AKI-opnamehoek (Elgato Key Light + GR18C RGB).
  1. Clean studio
  2. Storm
  3. Bollywood goud
  4. Hoge noot
  5. Silhouet → licht (variatie in de TikTok-hook)
  - Privé-pagina van Nitin, geen repo-bestand.
- **Opname-instellingen iPhone 18 (Pro):**
  - Blackmagic Camera-app, ProRes 422 HQ, Apple Log 2;
  - 4K verticaal, 25 fps, sluitertijd 1/50 (geen LED-flikker bij 50 Hz);
  - vaste witbalans gelijk aan de Elgato;
  - zonder Pro-model: HEVC SDR.
- **Resolve-advies:**
  - kleurbeheer DaVinci YRGB Color Managed;
  - input Apple Log 2 (of Apple Wide Gamut/Apple Log als die preset ontbreekt — nog te verifiëren in Resolve 21.1);
  - tijdlijn DaVinci Wide Gamut/Intermediate;
  - output Rec.709 Gamma 2.4;
  - SDR-levering voor sociale media.
- **Grens:** niets in Resolve gewijzigd. Huidige rechten: alleen `get_resolve_status`. Een preset of projectinstelling vraagt een aparte bouwtaak met Nitins akkoord.

## 4. Open punten voor ChatGPT

1. Nitins besluit over TikTok fase 1 (D11–D13) en welke captions.
2. Besluit over de inhaal-Instagram voor D06/D08/D09.
3. Uitzoeken waarom de geplande `-v3`-stagingtaken niet afgingen of geblokkeerd werden. Dit raakt D12–D14.
4. Eventuele bouwtaak voor een Resolve-projectpreset (Apple Log 2 → Rec.709, verticaal 25 fps): alleen als ChatGPT die specificeert en Nitin akkoord geeft.
5. Handmatig door Nitin:
   - TikTok-concept D10-V07 publiceren;
   - TikTok-foto D10-S3 plaatsen;
   - app-only quickwins (IG-links, pins, highlights; TikTok-pins).

## Beperkingen van deze update
- Dit is Claudes eigen verslag; geen onafhankelijke Codex-verificatie of Gemini-QC.
- Cijfers komen uit TikTok Studio, Make-executions en de datastore op de genoemde momenten.
- De oude toppers (6K–21K views, 2023–begin 2024): of die gepromoot waren is niet vastgesteld.
