# AKI V13 — daadwerkelijke A/B-previewbouw V01

## Opdracht en akkoord
Nitin gaf op 2026-10-02 om 09:30:07 Europe/Amsterdam expliciet akkoord ("dat is prima") op:
"Mag Claude Code beide previews bouwen en renderen in een aparte kopie van V13, inclusief de voorgestelde montage-, zoom- en captionwijzigingen? De originele V13, gelockte audio en kleur blijven behouden. Dit geeft geen toestemming voor publicatie."

Voer deze begrensde bouwopdracht uit in de lokale Claude Code-sessie. Lever twee afspeelbare video's op. Geen nieuwe algemene voorstelronde.
Dit document is een uitvoeringsbrief voor een interactieve lokale sessie, geen ondersteund inbox-taaktype van de automatische tekst-runner.

## Eerst lezen en controleren
Repository NitinBR1406/unchained-pipeline, broncommit 7116894f4e1b3df6c65a5d5615ea7d0c8f285d14.
Lees CLAUDE.md, toepasselijke instructies en p0e4/evidence/task_runs/pr_23/RESULT.json op deze commit.
Lees de bestaande renderer en contractbestanden:
- p0e4/resolve/render_aakhri_premium_style_sample_v02.py
- p0e4/resolve/aakhri_premium_style_sample_v02_contract.py
Gebruik die als technische referentie; voer de oude zes-secondenrenderer niet blind uit als nieuwe opdracht.
Verifieer lokaal bronproject, media, fontbestanden, logo, fps, kleurbeheer en bestaande toolrechten. Bewaar ongerelateerde wijzigingen.
Historisch bronproject: UNCHAINED_AAKHRI_FIRST_PUBLISH_PREVIEW_V13_CHAIN_CAPTION_REPAIR.
Verwachte V13 DRP SHA256: f1e720b658315418279dc27e913e695308d00bdd5b572dca05e1395170870bec.
Verwachte master SHA256: 7266506b3d9e5262ded0c579d664c2d6444e6c35c173cf00c062290810ffe088.
Gouden kettinglogo SHA256: 5e77eb7a6590d63fc33042cdfc62582f20a77d9bd6175868c77a3b8354a7b509.
Ontbrekende of afwijkende bronidentiteit moet eerst verklaard worden; gebruik geen willekeurige vervangende bron.

## Scope
Maak een nieuwe projectkopie en twee nieuwe timelines/uitvoermappen met unieke namen. Bewerk het originele V13-project niet.
Bouw hetzelfde 12-secondenfragment in A en B, voorlopig globale frames [60,420) bij 30 fps. Bevestig source/timeline-offsets lokaal; half-open notatie niet blind als Resolve API-in/out doorgeven.
A: rustig filmisch, drie visuele segmenten van nominaal vier seconden, langzame push-ins.
B: energiek, zes visuele segmenten van nominaal twee seconden, zichtbare reframes en korte punches op gemeten beats.
Behoud bronchronologie en audio; splitsen zonder zichtbare verandering telt niet als A/B-verschil.
Volg R2 voor de captions, kettinglogo en Cinzel/Montserrat. Lees de werkelijke bestaande tekst terug; verzin geen lyrics.
Schaduw/halo weglaten, tekst niet laten overlappen of gezicht bedekken.
Volledige 24-secondenoverlaybegroting uit R2 is uitsluitend ontwerpcontext; render nu de twee previews van 12 seconden. Claim geen full-clipcompliance op basis van die previews.
Geen Make, sociale uploads, publicatie, productiedeployment of automatische creatieve goedkeuring.

## Verplichte correcties op R2
- Definieer de B-punch additief als +3 procentpunten boven de gekozen basiszoom. Bij 118% basis is de piek 121%, niet 118%.
- Controleer alle pieken EN positieverschuivingen tegen werkelijke bronresolutie, safe crop, gezicht en hoofdruimte. Verlaag amplitudes indien nodig en leg de uiteindelijke waarden vast; maak geen ontbrekende beeldranden zichtbaar.
- De 2-secondenrasterposities zijn voorlopig. Gebruik geverifieerde beats waar haalbaar en rapporteer uiteindelijke grenzen/shotlengtes. Behoud exact dezelfde excerptduur en bronchronologie.
- Bronframecontinuiteit is een ontwerpmaatregel voor sync, geen bewijs dat lipsync goed is. Controleer bron-offsets en uiteindelijke audio/video.
- Controleer leesbaarheid van de werkelijke tekst in beweging; minimaal één seconde hold garandeert geen leesbaarheid.
- Maak onderscheid tussen eigen checks, onafhankelijk gecontroleerde uitkomsten en niet bewezen eigenschappen.

## Lokale rechten en uitvoering
De automatische runner en de bestaande Resolve-hook hebben alleen leesrechten. Het bouwakkoord maakt die technische instellingen niet vanzelf actief.
Gebruik bestaande lokale Claude Code/Resolve-capaciteiten. Geen permissiebypass, geen verwijdering van hooks, geen run_script_unsafe, geen alternatieve route om een geweigerde operatie alsnog uit te voeren.
Maak noodzakelijke uitbreiding concreet en beperkt tot deze projectkopieën, exact beoordeelde scripts en nieuwe outputs; behoud backups, log scope en herstel tijdelijke rechten na uitvoering.
Als een lokale tooltoestemming of afzonderlijke technische vrijgave nog nodig is, toon precies de geblokkeerde operatie en de kleinste vereiste wijziging. Geen generiek nieuw creatief akkoord vragen; Nitin heeft de beschreven bouw/render al goedgekeurd.
Wijzig geen gepinde automatische runner-, policy- of Master State-bestanden voor deze eenmalige uitvoering.
Controleer vóór mutatie dat geen ander proces dezelfde projectkopieën gebruikt.

## Oplevering
1. A_PREVIEW.mp4 en B_PREVIEW.mp4, elk exact 12 seconden met identieke bron-audioselectie, als afspeelbare reviewbestanden.
2. Nieuwe lossless intermediates indien nodig voor audiocontrole. Vergelijk de PCM van hetzelfde bronbereik; AAC niet als bit-identieke PCM behandelen.
3. Bewaar V13-kleurbeheer; voorkom een ongemarkeerde HDR/SDR-omzetting. Als een SDR-reviewversie nodig is, leg de conversie afzonderlijk vast.
4. Controleer volledige decode, duur/fps, frames, geluid, source-in/out, keyframes, daadwerkelijke visuele verschillen, leesbaarheid en captionoverlap. Sla hashes en eventuele beperkingen op.
5. Open de twee lokale reviewbestanden voor Nitin en geef exacte paden. Gebruik de bestaande private Shared Drive-reviewmap als die bereikbaar en geautoriseerd is; wijzig geen deelrechten. Geef alleen na geslaagde upload/readback echte kijklinks.
6. Leg uitvoeringsstatus en kleine receipt vast in een afzonderlijke evidence-PR. Geen ruwe logs/geheimen uploaden. Rapporteer een concrete blokkade als er geen video's zijn; noem een voorstel nooit een render.

Gemini leverde eerder een leeg antwoord bij CLI SUCCESS; er bestaat geen geldige Gemini-review van dit ontwerp. Dat blokkeert niet het maken van private previews, maar onafhankelijke creatieve QC blijft open.
PRODUCTION_DEPLOYMENT_AUTHORIZED = FALSE
PUBLICATION_AUTHORIZED = FALSE
FIRST_REAL_POSTER = PAUSED_BY_NITIN
