# Update voor ChatGPT (orchestrator), 25-11-2026

Van: Claude Code, de lokale bouwer. Nitin is de enige die iets goedkeurt.

Alles hieronder is privé testwerk:
- Er is niets gepubliceerd, gepland of geüpload.
- Er is niets aan Make veranderd.
- Er heeft geen onafhankelijke controle door Gemini plaatsgevonden; de controles zijn alleen die van Claude.

## 1. Surface Tracker-test in DaVinci Resolve

**Opdracht van Nitin:** "Test het door t zelf in resolve te doen met een png". Aanleiding was een TikTok-tip over de Surface Tracker.

**Akkoord:**
- Nitin gaf NITIN_CHANGE_APPROVAL voor alleen deze ene privétest. Claude mocht Resolve via schermbesturing bedienen in een nieuw project.
- Daarna keurde Nitin zelf de toegang tot Resolve en volledige schermbesturing goed.
- Bestaande projecten, originelen en V13 zijn niet aangeraakt.
- De update-melding naar Resolve 21.2 is overgeslagen.

**Opbouw:**
- Project `AKI_SURFACE_TRACKER_TEST_V01`, tijdlijn `SURFACE_TRACKER_V01` (1080×1920, 25 fps).
- Bron: een kopie van IMG_5950 (sha256 945be464…).
- Node 01 met de Surface Tracker. Output staat op "Warp Input 2 Onto 1". Input 2 is een gouden logo "UNCHAINED NITIN" als PNG met alpha, op 1080×1920.

**Verloop:**
- Eerste poging vanaf 0:00 mislukt. Tussen 3 en 8 s gaan de handen voor de borst langs en het raster ging met de handen mee.
- Tweede poging gelukt. De grens is getekend op 8:24 en vooruit gevolgd tot het einde; het raster bleef stabiel op de borst.

**Render:**
- Bestand: `SURFACE_TRACKER_TEST_V01.mov`, H.264, 1080×1920, 25 fps, 7,88 s. Bereik In 09:02 tot Out 16:23.
- Sha256: 145042c12019be81…
- Uitgelezen met ffprobe.

**Wat de test laat zien:**
- De techniek werkt op stof.
- Het werkt alleen waar de handen niet voor het logo komen.
- Een overlay-PNG moet het volledige frame beslaan (1080×1920) en een alpha-kanaal hebben. Anders rekt Resolve het logo uit en komt er een zwart vlak omheen.

**Open punt:**
- Nitin vroeg om het logo "iets kleiner" te maken.
- `LOGO_CHEST_1080x1920_V03_SMALLER.png` staat klaar: 300 px breed in plaats van 400, op dezelfde plek.
- Het moet nog in Resolve worden gewisseld en opnieuw gerenderd als V02. Daarvoor is opnieuw volledige schermbesturing nodig, maar die vraag is verlopen omdat Nitin niet achter zijn Mac zat.

**Vastlegging:** het akkoord, de hashes, de instellingen en de beperkingen staan in `.local/aki-surface-tracker-v01/APPROVAL_AND_RECEIPT_V01.md`.

## 2. Bekeken TikTok-tips (alleen advies)

- **Surface Tracker:** uitgevoerd, zie punt 1.
- **Witbalans in twee klikken (zwart- en witpunt):** lokaal getest op een frame van IMG_5950.
  - De neutrale punten (de zwarte hoodie en het chroom van de microfoon) waren al neutraal. De correctie was kleiner dan 1%.
  - Het oranje komt van het licht op de wand en is een bewuste sfeer.
  - Conclusie: de truc voegt niets toe voor de studiobeelden. Niet gebruiken op gelockte AKI-kleurversies (V13).
- **CLI-Anything (HKUDS, GitHub):**
  - Advies: nu niet installeren.
  - In het gelezen deel van de pagina staat geen kant-en-klare koppeling voor Resolve of CapCut, en Resolve heeft al een MCP.
  - Het installatieprogramma schrijft in `~/.claude`.
  - Volgens de governance mogen skills van derden niet aan de p0e4-repo worden gekoppeld.

## 3. Eerder in deze sessie (privé, niets gepubliceerd)

- **Digital twin en levende achtergronden:**
  - De achtergrond is vervangen door samengestelde beelden: een plate, daarop Wan-video en een VEED-matte. Dit is gedaan voor TALK4, D05 (met diepte en de echte microfoon teruggezet) en de proef met IMG_5950 voor de Erasmusbrug.
  - Kopieën staan in de Drive-map Twin, met gelijke hashes.
  - Nitins oordeel staat nog open.
- **Cover "Mangal Rang":**
  - Er zijn drie posterversies: V01 (4:5), V02 (9:16, echte foto, geen tilak) en V03 (sherwani in plaats van zwart hemd, echt gezicht teruggezet).
  - Nog niet op Drive gezet; Nitin moet de map nog kiezen.
  - Voor de licentiestatus van de cover is nog geen antwoord.
- **Hedra:** tegoed $10,67 van het pakket van $20.

## Status

- PRODUCTION_DEPLOYMENT_AUTHORIZED = FALSE
- PUBLICATION_AUTHORIZED = FALSE, behalve expliciete goedkeuringen per post
- FIRST_REAL_POSTER = PAUSED_BY_NITIN

Er is geen nieuwe bouwtaak gestart en geen goedkeuring namens Nitin aangenomen.
