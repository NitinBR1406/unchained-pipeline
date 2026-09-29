# UNCHAINED NITIN — Premium productie en kwaliteitscontrole
## Uitvoeringsplan V01 — 29 september 2026

Status: PLAN_UITGEWERKT; niet automatisch goedgekeurd voor uitvoering, aankoop, deployment of publicatie.
Nitin vroeg om volledige uitwerking van het zevenstappenvoorstel.
Broncommit: 24ffeeb66c1e59df01abf1f8ddaf53e126460b1e.
Voorgaand onderzoeksbrief: p0e4/evidence/premium_qc_research_v01/RESEARCH_BRIEF_V01.json.
Campagneplan: p0e4/evidence/cover_campaign_research_v01/AAKHRI_14_DAY_CAMPAIGN_PLAN_V01.md.

## 1. Doel, bestaande toestand en grenzen

Doel: een aantoonbaar mooiere Aakhri Ishq-post én een herbruikbare werkwijze voor iedere volgende cover, video, foto en carrousel. Tijdwinst moet in actieve montagetijd, wachttijd en herstelwerk worden aangetoond; geen ongefundeerde belofte van autonome foutloze creativiteit.

Bewezen vóór dit plan:
- Resolve-rendering van V13 en de korte A/B-stijlproeven.
- Claude-planontvangst en Gemini actual-asset review via bestaande routes.
- Herstel Master State V16.20/state_version 46 met deterministische replay en 19 gerichte tests.
- Een beperkte controllercontroletaak en idempotent heraanbod.

Niet bewezen:
- Algemene automatische ontvangst/uitvoering van nieuwe Resolve-opdrachten.
- Template- en markerautomatisering voor alle gewenste effecten.
- Gekalibreerde kleurbeoordeling en betrouwbare AI-QC zonder gemiste fouten.
- Een afgeronde nieuwe kleur-/captionrichting.

A/B-keuze blijft open. Het nieuwe onderzoek maakt explicieter verschillende opties; bestaande A/B wordt als referentie hergebruikt, niet alsnog stilzwijgend afgekeurd of goedgekeurd.
Nieuwe kleurproeven zijn uitsluitend geïsoleerde kandidaten. Bestaande gelockte master, audio, bronmedia, logo en bevroren P0-E0–P0-E3 blijven ongewijzigd.
Geen nieuwe scheduler, abonnement, aankoop, plugininstallatie of productiedeployment door dit document.
PUBLICATION_AUTHORIZED=false; PRODUCTION_DEPLOYMENT_AUTHORIZED=false; FIRST_REAL_POSTER=PAUSED_BY_NITIN.
Een stijlakkoord is geen akkoord voor ieder toekomstig bestand en geen publicatieakkoord.

## 2. Productiedoel en tastbare oplevering

De pilot levert:
1. Gecontroleerde capabilitymatrix van de daadwerkelijke Mac/Resolve-installatie.
2. Maximaal drie bruikbare templatekandidaten met previews, licentie/dependencies en integratie-inschatting.
3. Twee kleurproeven plus huidige referentie op één identiek fragment.
4. Drie duidelijk verschillende captionbehandelingen op één gedeelde beeldbasis.
5. Eén gekozen gecombineerde proef vóór volledige uitwerking.
6. Een herbruikbare markerconventie en bewezen uitvoerbare mapping.
7. QC-benchmark met schone controles en bekende foutgevallen.
8. Eén volledig postpakket: video, cover, passende foto-/carrouselvormgeving, tekst/credits en exacte exportidentiteit.
9. Template-releasecandidate, resultatenrapport en tijdmeting op een tweede cover.
Geen volledig veertiendaags pakket ontstaat automatisch uit deze pilot.

Premium betekent in deze pilot: natuurlijke huid, consistente shots, gecontroleerde highlights, goed leesbare expressieve typografie, muzikale beweging, exact juiste merkassets, sterke opening en einde, verzorgd geluid en samenhang tussen alle postvormen. Een donkere/gouden look is een richting, geen voldoende kwaliteitsbewijs.

## 3. Werkpakketten

### WP0 — Intake en vastzetten proefbasis
Eigenaar: Work/Codex; regie: ChatGPT.
- Lees actuele instructies en huidige queue. Controleer actieve taak/lock; geen dubbel werk.
- Inventariseer geïnstalleerde Resolve Studio-versie/build, OS, beschikbare fonts/effects en bestaande scripts/templates.
- Bind V13 en bronproject/bronmedia/audio/logo aan hashes.
- Selecteer één representatief fragment van 10–15 seconden: huid, schaduw, highlight, duidelijke frase, muzikale overgang en ruimte voor tekst. Gebruik dezelfde frames in alle vergelijkingen.
- Inspecteer of een schoon pre-grade bronpad bestaat. Niet blind een nieuwe LUT over een gebakken grade zetten. Is alleen de afgewerkte master beschikbaar, beperk de proef tot verantwoord trimmen en vermeld dit.
- Bewaar bestaande V13/A/B en maak een geïsoleerde kandidaatprojectkopie.

Oplevering: INPUT_BINDING_V01.json + CAPABILITY_MATRIX_V01.csv.
Acceptatie: elk benodigd bronbestand beschikbaar en geverifieerd; ontbrekende bytes expliciet geblokkeerd.

### WP1 — Bestaande templates selecteren
Eigenaar: Claude voor implementatiereview; Work/Codex voor lokale verificatie.
- Begin bij aanwezige Fusion/Text+-titels en native Animated Subtitles.
- Bekijk maximaal drie kandidaten voor captions/motion, waaronder native hergebruik en zo nodig een externe macro.
- Beoordeel echte preview op 9:16, fontvervanging, verschillende tekstlengtes, transparantie, text-safe zones, performance, afhankelijkheden, commerciële licentie en hergebruik over covers.
- Markeer elke capability afzonderlijk: native beschikbaar, scriptbaar getest, UI-only, externe adapter nodig of niet beschikbaar.
- Een beat-snapping functie bewijst geen volledige auto-edit, en een marketplacevideo bewijst geen compatibility.
- Leg exacte versie en parameters vast. Geen betaalde asset aanschaffen zonder concrete kosten- en licentiegoedkeuring.
- Claude reviewt vóór productiecode/render. Als reactie uitblijft: documenteer dat en doe onafhankelijke read-only inventarisatie; claim geen voltooid gezamenlijk review.

Selectiescore als rangschikking, niet als eindgoedkeuring:
visuele geschiktheid 30%, herbruikbaarheid 25%, automatisering 20%, robuustheid/prestaties 15%, licentie/onderhoud 10%.
Kritische licentie-, compatibiliteits- of fontfout kan niet met een hoge totaalscore worden gecompenseerd.

Oplevering: TEMPLATE_SHORTLIST_V01.md, previewlinks en recommendation.
Stopregel: één primaire oplossing plus één fallback; geen onbeperkte templatezoektocht.

### WP2 — Twee kleurproeven
Eigenaar: lokale uitvoering; onafhankelijke beoordeling: Gemini, met expliciete kijkbeperkingen.
Variant C1 Warm cinematic: warme highlights, natuurlijke huid, rijke donkere achtergrond met detail, zachte highlight-overgang.
Variant C2 Dramatic stage: krachtiger contrast, meer subject/achtergrondscheiding, gecontroleerd koelere schaduwen en warme huid.
Dit zijn creatieve instructies; niet beweren dat deze looks al passen zonder broninspectie.

Methode:
- Controleer input color space/gamma en project/outputtransforms.
- Scheid basisnormalisatie, shot matching, creatieve look en outputtransform.
- Geen automatische beauty/face reshape. Behoud huidtextuur en identiteit.
- Geen wijzigingen in audio, takekeuze, montage of tekst voor de kleurvergelijking.
- Lever bewegende vergelijkingen en referentiestills met dezelfde frame-ID's.
- HLG blijft apart geïdentificeerd. Indien SDR-proef nodig is: een juiste afgeleide transform, geen alleen-herlabelen.
- Controleer op hetzelfde scherm onder consistente instellingen; schakel adaptieve schermweergave waar passend uit. Een telefoon is een praktische consumentencheck, geen gekalibreerde referentiemonitor.
- Vermeld wanneer calibrated HDR-evaluatie niet beschikbaar is. Geen monitor aankopen binnen dit plan.

Acceptatie: geen ongewenste clipping/crush/kleurzweem, behoud huiddetail, geen schokkende shotverschillen; tolerantie per bron en referentie vaststellen. Geen universele huidhelderheidsgrens opleggen.
Nitin kiest C1/C2 of geeft één gebundelde correctie. De locked baseline wordt daardoor nog niet vervangen.

### WP3 — Drie captionbehandelingen
Eigenaar: Claude ontwerp/implementatieadvies, Work/Codex uitvoering.
Alleen captions variëren; dezelfde neutrale/gecontroleerde kleurreferentie en dezelfde tekst/tijden.

T1 Lyrische elegantie: korte frase, verfijnde onthulling, één gouden accentwoord.
T2 Kinetische impact: duidelijk groter accentwoord, korte gerichte beweging op een gevalideerd muzikaal accent.
T3 Filmische titelstijl: expressieve Cinzel SemiBold-songtitel met leesbare Montserrat-frases en vaste hiërarchie.

Vaste voorwaarden:
- Bestaande fonts/merkidentiteit als uitgangspunt; alternatieve fontfamilie alleen apart voorleggen.
- Onderscheid lyric subtitles, brand/title overlays en platformposttekst.
- Liedtekst alleen uit geverifieerde bron/transcript en noodzakelijke rechtencontext; Hindi-zangtiming niet blind uit speech transcription overnemen.
- Geen continue captions over de hele performance om de proef te laten opvallen.
- Maximaal twee leesbare regels als ontwerprichting, geen starre regel die zinsbetekenis vervormt.
- Letters scherp; geen brede schaduwwaas; subtiel functioneel contrast mag worden getest.
- Geen tekst over mond/ogen en geen overlap met platform-UI.
- Controleer korte/lange frases en eventuele gebruikte schriften; ontbrekende glyphs blokkeren.
- Proeven tellen niet als drie extra campagnevideo's.

Oplevering: captionvergelijking, exact tekst/timingbestand, parameters en interne defectcontrole.
Nitin kiest T1/T2/T3 of één gerichte wijziging. Combineer daarna gekozen C en T in één korte proef. Geen zes volledig gerenderde combinaties.

### WP4 — Markerconventie en uitvoering
Eigenaar: Work/Codex, Claude review vóór implementatie.
Herbruik bestaande editplan/operation-contracten; voeg geen alternatieve besturingslaag toe.

Markercontract bevat minimaal: schema_version, source_sha, timeline_fps, start/end_frame, marker_id, type, evidence/source, tekst of asset_ref, template_version en conflict_policy.
Werk met ondubbelzinnige frame-intervallen volgens bestaand contract. Leg eindframe-conventie expliciet vast om off-by-one fouten te voorkomen.

Mapping:
- HOOK: korte openingstitel uit goedgekeurde macro.
- PHRASE_START/END: geverifieerde captionperiode.
- ACCENT: accentwoord of begrensde schaalbeweging.
- CLIMAX: expliciete cut/push-in uit bestaande toegestane editoperaties.
- OUTRO: bestaande hash-bound logo/outrocombinatie.

Beatmarkers vormen suggesties; muziekfrasen en expressie bepalen selectie. Niet op iedere beat knippen. Geen bewering dat ieder beatpunt een kick/snare is.
Geautomatiseerde toepassing alleen waar API/UI-route op dit host bewezen is. Fallback mag een vaste handmatige plaatsingshandeling zijn, eerlijk gemeten.
Conflicten: gezicht/mond vrijhouden gaat vóór decoratie; geen twee gelijktijdige captionblokken; audio en synchronisatie nooit stilzwijgend aanpassen.
Onbekende marker/asset/templateversie: HOLD in plaats van improvisatie.
Eerst geïsoleerde dry plan, daarna korte private render, daarna pas volledige clip.

Oplevering: marker schema/mapping, capabilitybewijs, renderreceipt en herhaalbaarheidstest.
Acceptatie: dezelfde inputs geven hetzelfde editplan; juiste framegrenzen; geen dubbele plaatsingen op heraanbod. Geen bitidentieke video claimen tenzij gemeten.

### WP5 — Kwaliteitscontrole valideren
Eigenaar: Work/Codex technische checks; Gemini onafhankelijke creatieve QC; Nitin creatieve referentiestandaard.

Drie fasen:
A. Preflight op bron, template, kleurpipeline, tekst/font, geometrie, timing en assetidentiteit.
B. Post-render checks op exact bestand: volledige decode, streams, duur, frameaantal, audio, transitions en afwijkingen.
C. Actual-asset creatieve review: volledige pilot afspelen; relevante overgangen framegewijs inspecteren; timestamp + waarneming + confidence + beperking.

Benchmark:
- Schone door inspectie bevestigde controles én disposable foutvarianten.
- Fouttypen: verkeerd logo, captioncollision, font/glyph fallback, mondbedekking, cropdrift, verkeerde outputtransform/tagging, lipsyncoffset, onbedoeld zwart/freeze, audio-onderbreking, onleesbare tekst.
- Geen schadelijke kopieën in de publicatiequeue.
- Scheid ontwikkelvoorbeelden en held-out acceptatieset; blind labels voor beoordelaar.
- Leg ground truth vast met menselijke verificatie voor ambigue/perceptuele items.
- Meet misses per defectklasse, false alarms, reviewduur en repairduur; geen gemiddelde score die kritische miss maskeert.
- Alle kritische bekende fouten in de afgesproken held-out set moeten blokkeren; dit is geen universele foutloosheidsgarantie.
- Tegenstrijdige beoordelingen -> UNRESOLVED/HOLD met concrete hertoets; geen simpele meerderheid van AI-antwoorden.
- OCR, face tracking en AV-sync detectors zijn kandidaatchecks totdat recall/false alarms op dit materiaal zijn gemeten.
- Onverifieerbare HDR/lyric/perceptual aspecten expliciet NOT_VERIFIED.

Creatieve rubric, elk met beschrijving en voorbeeld: performanceprioriteit, emotionele montage, typografie/leesbaarheid, kleur/natuurlijke huid, merkconsistentie, opening/einde.
Voorstel acceptatie: geen kritisch defect, geen ontbrekende essentiële evidence, gekozen stijl conform referentie en Nitin finaal akkoord. Geen willekeurig 90/100 als vervangende goedkeuring.

Oplevering: QC_BENCHMARK_REPORT_V01.md + exact-file reviews + foutbibliotheek + bekende beperkingen.

### WP6 — Compleet postpakket en template-releasecandidate
Eigenaar: Work/Codex productie, ChatGPT samenhang.
- Eén complete private Aakhri-post met gekozen richting en volledige QC.
- Coverbeeld, foto-/carrouselontwerp en posttekst laten aansluiten op typografie, kleuren en beeldtaal.
- Gebruik bestaande echte foto's indien geschikt; geen fictieve backstage/publieksreacties. Ontbrekende fotografie expliciet opnemen in opnameplan.
- Maak alleen de benodigde platformexports; aspect ratio/tekstzones/kleurweergave/loudness per export verifiëren. Geen universeel social-loudnessgetal uit de lucht grijpen.
- Bron -> project/template -> master -> derivative lineage, hashes en reviewbewijzen opslaan.
- Full-clip performancecoverage meten: geldend hard 80%-contract respecteren, minimaal 75% zonder tekst/graphics; leg meetdefinitie vast. Een korte captionproef bewijst dit niet.
- Onderhoud max zes unieke videoderivaten, dagelijkse campagnecadans en volgende-coverbuffer.
- Template vastzetten pas na creative/video/stijlbesluiten met exact toepassingsbereik; geen toekomstige publicatiegoedkeuring afleiden.
- Gecontroleerde technische template-update krijgt nieuwe versie met regressie op bekende foutgevallen.

Oplevering: POST_PACKAGE_MANIFEST_V01.json, exact preview/cover links, QC, template-releasecandidate, gebruikerswijzigingen en open gates.

### WP7 — Snelheid bewijzen op volgende cover
Eigenaar: Work/Codex met regie ChatGPT.
- Volgende cover kiezen uit werkelijk beschikbare catalogus, zonder fictieve gereedheid.
- Zelfde templates; bronintake/shot matching en captions per cover controleren.
- Meet actieve edit, queuewait, render, interne rework, reviewtijd en human wait afzonderlijk.
- Vergelijk gelijke deliverables/complexiteit en splits eenmalige templatebouw van terugkerende productietijd.
- Richtdoel: minimaal 30% minder actieve edit + interne rework versus gemeten vergelijkbare baseline, zonder kwaliteitsverlies; een hypothese, geen belofte.
- Geen baseline beschikbaar: pilot wordt baseline; besparingsclaim pas na herhaling.
- Richtdoel: één gebundelde creatieve correctieronde. Nieuwe creatieve scope apart houden.
- Bij falen: rapporteer feitelijke bottleneck en één begrensde verbetering, niet weer een complete redesign.

## 4. Volgorde, rollen en tijdsbudget

Uitvoeringsvolgorde:
WP0 -> WP1 -> WP2 en WP3 als losse vergelijkingen -> Nitin-keuzes -> gecombineerde korte proef -> WP4 -> WP5 -> WP6 -> WP7.
WP5-testontwerp kan tijdens WP1 starten; géén renderer/QC-dubbelwerk op dezelfde mutable projectkopie.

Rollen:
- ChatGPT: prioriteiten, samenvoegen bewijs, voorstellen, scopebewaking; geen onbewezen dispatchclaims.
- Work/Codex: actuele hostinspectie, implementatie, render, tests, herstel, diff, evidence en state.
- Claude: concrete template/automatiseringsreview en integraties; aantoonbare ontvangst vóór claim van betrokkenheid.
- Gemini: onafhankelijke visuele/creatieve vergelijking op echte bestanden via afgesproken route.
- Nitin: creatieve richting, nieuwe kosten en vereiste change/release/publicatiebesluiten.
Geen nieuwe agent of permanent proces nodig om deze rolverdeling te beschrijven.

Voorlopige tijdsbudgetten voor actieve uitvoering, te herijken na WP0; geen kalenderbelofte:
WP0 0,5–1 uur; WP1 1–2 uur; WP2 1–2 uur; WP3 1–2 uur; WP4 1–3 uur; WP5 2–4 uur; WP6 1–2 uur; WP7 1–2 uur voor validatie boven op bronafhankelijke coverproductie.
Totaal indicatief 8,5–18 uur eenmalige inrichting/validatie; wachttijd, eventuele nieuwe opname, grote API-gaten en aanvullende bronherstel niet inbegrepen.
Als markeradapter meer dan drie uur nieuwe ontwikkeling vraagt: stop uitbreiding, lever bewezen templateworkflow en ontwerpbesluit; voorkom dat content blijft wachten op engineering.
Voorgestelde werksessies: (1) intake + shortlist; (2) kleur/captionvergelijkingen; (3) keuze + korte gecombineerde proef; (4) marker/QC/pilot; (5) tweede-covermeting.
Na elke sessie tastbaar resultaat en werkelijk resterende blokkade, niet alleen statusdocumentatie.

## 5. Automatische ontvangst apart behandelen

Huidige NEXT_READY vraagt beperkte NITIN_CHANGE_APPROVAL voor heartbeat -> engineering.py op de bestaande V11-allowlist. Dit plan verleent die niet.
Zelfs na die wijziging is algemene Resolve-automatisering niet bewezen of geautoriseerd door die beperkte controlleracceptatie.
Ontvangststatus per werkpakket: PREPARED, DELIVERED, ACKNOWLEDGED, RUNNING, EVIDENCE_VERIFIED, WAITING_FOR_NITIN.
Een GitHub-bestand aanmaken betekent alleen PREPARED. Bij ontbrekende transportverbinding niet beweren dat Claude/Gemini/worker begonnen is.

## 6. Risico's en praktische terugval

- Alleen baked grade beschikbaar: geen agressieve LUT-stapeling; beperkt trimmen of juiste bron opvragen.
- Template afhankelijk van betaald effect: native alternatief eerst; concrete aankoopbeslissing apart.
- Marker-API onvoldoende: voorgeschreven UI-handeling meten en documenteren; geen nieuwe onbewezen bridge.
- Liedtranscript onzeker: geverifieerde frase of alleen songtitel/brandtekst; geen verzonnen lyrics.
- Browserkleur onzeker: representatieve target-devicecheck en expliciete HDR-beperking.
- AI-QC tegenstrijdig: timestampbewijs herbeoordelen; nooit automatisch groen.
- Brontekst/asset ontbreekt: onafhankelijk READY werk doorzetten.
- Scope groeit: nieuwe ideeën in backlog; pilot krijgt vaste oplevering.

## 7. Bronnen en toetsbare claims

Blackmagic Resolve 20 New Features Guide:
https://documents.blackmagicdesign.com/SupportNotes/DaVinci_Resolve_20_New_Features_Guide.pdf
Beschrijft beatdetectie/snapping, Animated Subtitles en Fusion-styling. Bewijst geen API-capability op de huidige host.
Blackmagic Color:
https://www.blackmagicdesign.com/products/davinciresolve/color
Motion Array templatecatalogus:
https://motionarray.com/davinci-resolve-templates/
Motion Array macros versus templates:
https://help.motionarray.com/hc/en-us/articles/9332484052509-DaVinci-Macros-vs-Templates
Voorbeeldkandidaat, nog niet getest of gekocht:
https://motionarray.com/davinci-resolve-templates/dynamic-kinetic-typography-1108903/

Geen nieuwe gezamenlijke Claude/Gemini-review of render uitgevoerd voor dit document.
