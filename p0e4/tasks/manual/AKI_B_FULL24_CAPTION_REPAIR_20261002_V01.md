# AKI B — volledige private preview en captionherstel V01

## Besluit en opdracht
Nitin koos op 2026-10-02 in de Work/Codex-conversatie expliciet: "B past Beter bij mij!"
Daarna keurde hij met "goed plan!" het vervolg goed: captions beter leesbaar maken, B doortrekken naar de volledige 24 seconden en leesbaarheid/lipsync controleren.
Dit is een stijlselectie en begrensde private bouwopdracht, geen final approval of publicatieakkoord.
Voer uit in de bestaande interactieve lokale Claude Code-sessie. Maak één volledige B-reviewvideo; geen nieuwe A/B-keuzeronde.
Dit is een handmatige uitvoeringsbrief, geen automatische inbox-taak. Een merge start geen Resolve-render.

## Gebonden bronnen
Repository: NitinBR1406/unchained-pipeline.
Governancebasis: caae20483495294d2bf6b185b94cddc67ecd23f8.
Lees CLAUDE.md, de aangewezen Master State, toepasselijke instructies en de eerdere manual brief AKI_V13_AB_PRIVATE_BUILD_20261002_V01.md.
Succesvolle R4-code en evidence: PR26, exact commit 5e4f60fdfdfbbda290ac5c0afc0ca7deb163125b, directory p0e4/evidence/aki_v13_ab_preview_build_v01/.
PR26 was bij het opstellen open; haal deze exacte bron apart op en veronderstel niet dat de basisbranch R4 bevat. Geen reset van lokale wijzigingen.
Lees BUILD_STATUS, CODEX_REVIEW_V04.md, de scripts/tests, STEP3_MEDIA_QC_R4.json en checksums vóór wijzigingen.
Gekozen B_PREVIEW.mp4 SHA256: 8c7c3886d3969e580a833e9396c06de9a80cbe48d69d0581e1806017fb3d6eff.
Private B-referentie: https://drive.google.com/file/d/1EsoAsWc8_OEuTVGVbXR-AtnCelHCukM_/view
R4-project: UNCHAINED_AKI_V13_AB_PREVIEW_BUILD_V01.
R4-B-timeline: AKI_V13_AB_B_RHYTHMIC_R4.
Originele V13 DRP SHA256: f1e720b658315418279dc27e913e695308d00bdd5b572dca05e1395170870bec.
V13-master SHA256: 7266506b3d9e5262ded0c579d664c2d6444e6c35c173cf00c062290810ffe088.
Kettinglogo SHA256: 5e77eb7a6590d63fc33042cdfc62582f20a77d9bd6175868c77a3b8354a7b509.

## Bouw
Maak een nieuwe geïsoleerde projectkopie, unieke timeline en nieuwe uitvoermap voor AKI_B_FULL24_CAPTION_REPAIR_V01.
Behoud oorspronkelijke V13, alle A/B-versies en bestaande outputs. Controleer projectidentiteit en actieve locks vóór mutatie.
Render de volledige V13-selectie: globale frames [0,720) bij 30 fps, exact 24 seconden, 1080x1920.
Verifieer lokale Resolve-in/out-semantiek en oorspronkelijke video/audio-offsets. Behoud bronchronologie, gelockte audio, kleurbeheer en bronmedia.
Gebruik het gekozen ritmische B-karakter: zichtbare reframes en korte zoomaccenten. Breid bewust uit over 24 seconden; een knip zonder zichtbare verandering telt niet als ritmische verandering.
Gebruik gemeten beats waar beschikbaar. Rapporteer anders timing als benadering; claim geen bewezen beat-sync op basis van een aangenomen BPM.
Behoud de bewezen R4-aanpak voor Fusion-vervanging, splinebenaming en weggelaten defaultwaarden. Verwar receipt-revision 3 uit R4 niet met een oudere scriptversie.
R4 relatieve maximale zoom was 1.15 inclusief additieve punch van 0.03. Overschrijd dit niet zonder aantoonbare noodzaak en cropcontrole; verlaag waar hoofdruimte of beeldranden dat vragen.
Controleer ook nieuwe intervallen, pieken en verschuivingen, niet alleen de reeds gerenderde 12 seconden.

## Captionherstel
Bekend gebrek uit Claude's eigen R4-QC: lichte letters verliezen contrast op huid/licht overhemd, vooral rond 2 seconden van de B-excerpt (globaal circa 4 seconden).
Verbeter positie in een stabiel donker beeldgebied en waar nodig gewicht/grootte. Houd het gezicht vrij; geen schaduw/halo, geen tekstoverlap.
Controleer op normale afspeelsnelheid én relevante frames in de correct geïnterpreteerde kleurweergave. Een ongetonemapte HLG-JPEG is geen afdoend oordeel over de video.
Behoud bestaande tekst exact:
- Hook: SOME LOVE STORIES / NEVER REALLY END. (bestaande tweeregelige tekst)
- Titel: AAKHRI ISHQ
- Artiest: UNCHAINED NITIN
Behoud gouden kettinglogo; geen bliksemlogo. Controleer daadwerkelijke fontresolutie voor Cinzel/Montserrat en rapporteer een ontbrekend font zonder stilzwijgende vervanging.
R2-full24-ontwerp is startpunt: intrologo [0,30), hook [90,150), outro logo/titel/artiest [672,720).
Deze vensters zijn nog niet bewezen in een full24-render. Pas binnen de opdracht aan als leesbaarheid dat vereist; meet de unie van alle overlayframes inclusief fades.
Hard minimum 75% beeld zonder overlays; streef 80%. Startpunt geeft 138/720 overlayframes (80.83% vrij). Rapporteer werkelijke vensters/uitkomst; een korte hold is niet automatisch leesbaar.

## Rechten
Het creatieve bouwakkoord wijzigt geen technische toolrechten.
Gebruik uitsluitend ondersteunde lokale toestemmingen voor deze concrete taak en beoordeelde scripts. Geen deny/hook-bypass, run_script_unsafe of algemene rechtenuitbreiding.
Als benodigde rechten ontbreken, toon de exacte operatie en kleinste taakgebonden wijziging via de bestaande lokale toestemmingsroute. Vraag geen nieuwe creatieve selectie.
Herstel tijdelijke rechten na afloop. Wijzig geen automatische runner, gepinde policy of Master State.

## Oplevering en controle
1. Eén afspeelbare B_FULL24_PREVIEW.mp4, exact 720 frames/24 seconden; noodzakelijke hoogwaardige intermediate en aparte gemarkeerde SDR-reviewversie alleen indien nodig.
2. Controleer volledige decode, fps/duur, audio, broncontinuïteit, keyframes, hoofdruimte, zwarte randen, captions in beweging, logo en werkelijk overlaybudget.
3. Vergelijk PCM met exact de volledige V13-audioselectie. AAC is geen bit-identieke PCM; behoud en controleer A/V-offsets. Broncontinuïteit of audiohash bewijst geen menselijke lipsync; vermeld wat werkelijk visueel gecontroleerd is.
4. Bewaar compacte receipt met taak-/sessie-ID, exacte source/script/outputhashes, bron- en timeline-identiteit, tijden, eigen controles, onafhankelijke controles en beperkingen. Geen ruwe logs/geheimen.
5. Open de lokale video voor Nitin. Bewaar binnen de reeds gebruikte private reviewlocatie op Shared Drive met een nieuwe versiemap, uitsluitend bestaande toegang en zonder deelrechten te veranderen. Verifieer aflevering/readback en geef pas dan de echte kijklink. Meld afzonderlijk of contenthash op server of alleen via lokale mount is gecontroleerd.
6. Lever wijzigingen en compacte evidence via een nieuwe PR. Geen automatische claim van onafhankelijke Gemini-QC, Nitin-final-approval of publicatie.
Bestaande R4-QC is Claude's eigen controle; Work/Codex heeft de broncode technisch beoordeeld maar de video's niet onafhankelijk bekeken. Er is nog geen geldige Gemini-QC voor dit ontwerp.
Status blijft private review totdat het daadwerkelijke resultaat is beoordeeld.

PRODUCTION_DEPLOYMENT_AUTHORIZED = FALSE
PUBLICATION_AUTHORIZED = FALSE
FIRST_REAL_POSTER = PAUSED_BY_NITIN
