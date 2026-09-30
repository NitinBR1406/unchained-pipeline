# AI-rollen en communicatie — V01

Datum: 2026-09-30 (Europe/Amsterdam)
Project: UNCHAINED NITIN — AI OPERATING SYSTEM
Status: vastgelegde werkafspraak; technische activering en ontvangst door Claude/Gemini NIET bevestigd.

## Aanleiding en reikwijdte
Nitin heeft in deze sessie Claude als builder bevestigd en vraagt om een duidelijke inrichting van ChatGPT, Claude en Gemini met communicatieregels. Dit document concretiseert die rolverdeling voor de premium Resolve-productie. Het vervangt voor nieuwe opdrachten binnen die scope de eerdere taakverdeling waarin Work/Codex bouwde en Claude uitsluitend reviewde. Historische resultaten worden niet herschreven.
Dit document wijzigt geen software, heartbeat, frozen P0-E0–P0-E3, publicatie- of deploymentgate. Het is geen bewijs van werkende autonome uitvoering of een Master State-transitie.

## Rollen
| Rol | Verantwoordelijkheid | Grens |
|---|---|---|
| Nitin | Eigenaar, creatieve richting, expliciete human gates | Geen routinematige AI-naar-AI berichtenkoerier |
| ChatGPT / 00 MASTER ORCHESTRATOR | Eén opdracht, prioriteit, scope, acceptatiecriteria, taaktoewijzing, samenvoegen reviews en status aan Nitin | Geen creatieve goedkeuring namens Nitin; geen onbewezen uitvoeringsclaims |
| Claude / builder | Inspectie van werkelijke Resolve-projecten, implementatie, rendering en herstel in geïsoleerde kandidaten | Eigen controles gelden niet als onafhankelijke review; uitsluitend toegewezen scope |
| Work/Codex / technische verifier | Code- en bewijscontrole, relevante regressie, bestandsidentiteit, decode en instellingencontrole; integratiediagnose | Neemt de Resolve-build niet stilzwijgend over en muteert niet gelijktijdig dezelfde kandidaat |
| Gemini / creatieve en platform-QC | Onafhankelijke beoordeling van echte media; concrete defecten, tijdcodes, beperkingen en voorkeuren | Geen Nitin-approval; technische of subjectieve onzekerheid expliciet |

Eén organisatie kan meerdere rollen huisvesten, maar rapporten benoemen altijd de concrete uitvoerende sessie/host en rol. Ontvangst door Claude Code is niet automatisch ontvangst door een bestaande Claude Dispatch-context.

## Bronnen en routes
1. GitHub NitinBR1406/unchained-pipeline, versioned Master State en SHA-gebonden evidence zijn de technische autoriteit.
2. Google Shared Drive “Unchained Nitin — Master” bewaart productieassets volgens de bestaande procedure.
3. Repositorytaak en evidence vormen de overdracht; een chat bevat alleen de gerichte opdracht en verwijzingen, niet een concurrerende state.
4. Claude: gebruik de bestaande project/Dispatch-context voor continuïteit. Verifieer welke concrete lokale Claude-client toegang heeft tot Resolve. Een noodzakelijke overgang naar een lokale builder-sessie krijgt een expliciete parent-task/context-verwijzing en eigen ontvangstbewijs. Geen stille contextwissel.
5. Gemini: gebruik de bestaande chat https://gemini.google.com/app/7c9afdcb27030bcb (“YouTube-groeistrategie unchainednitin”). Geen losse nieuwe chat voor hetzelfde werk.
6. Een Drive-link is geen bewijs dat media bekeken kunnen worden. Registreer daadwerkelijke bestandstoegang en het exact beoordeelde bestand.
7. Gebruik voor Claude ↔ Resolve eerst de native AI-assistentintegratie van Studio 21.1, na lokale verificatie. Productondersteuning is geen bewijs dat deze route op de Mac actief is.
8. Bij ontbrekende transporttoegang: rapporteer BLOCKED met de concrete ontbrekende koppeling. Een opgeslagen verzoek is nooit SENT, RECEIVED of RUNNING zonder passend bewijs.

## Minimale opdracht en berichten
Elk werkpakket bevat:
- task_id, revision, parent_task_id (indien van toepassing), assigned_role en concrete executor zodra bevestigd;
- base_commit, Master State-verwijzing, project/timeline-identiteit en exacte input-SHA256;
- doel, toegestane wijzigingen, verboden effecten, acceptatiecriteria en bestaand tijd-/retrybudget;
- outputlocaties, afhankelijkheden, reviewrollen en toepasselijke human gates.

Elk bericht bevat task_id/revision, event_id, berichttype, afzender/ontvanger, timestamp in UTC, artifactverwijzingen en eventuele blocker/next_action.
Berichttypen: REQUEST, ACK, PROGRESS, RESULT, DEFECT, BLOCKED, REVIEW_RESULT.
ACK noemt de werkelijk beschikbare host/client, inputrevisie en capaciteiten. Geen ACK namens een andere AI.
Bewaar volledige reviewreacties met provenance; een samenvatting vervangt het bronbewijs niet. Geen tokens of secrets in berichten/evidence.

## Werkcyclus en statusbetekenis
Dit zijn proceslabels; zij introduceren geen nieuwe eventtypes in de bestaande reducer.
DRAFT → READY → SENT → ACKNOWLEDGED → RUNNING → BUILT → IN_REVIEW → REVIEWED_READY_FOR_NITIN.
Bij defect: IN_REVIEW → REPAIR_REQUIRED → RUNNING → BUILT → IN_REVIEW.
BLOCKED benoemt de echte afhankelijkheid. WAITING_FOR_NITIN is uitsluitend voor een echte human gate.
- READY: opdracht compleet en binnen geautoriseerde scope.
- SENT: aantoonbare verzending via de bestaande route.
- ACKNOWLEDGED: concrete uitvoerder bevestigt ontvangst; geen aanname uit een bestand.
- RUNNING: aantoonbare start met uitvoeringsbewijs.
- BUILT: resultaat en hashes bestaan; nog geen onafhankelijke PASS.
- REVIEWED_READY_FOR_NITIN: vereiste onafhankelijke checks afgerond, geen onopgelost kritisch defect, beperkingen expliciet.
- Creatieve selectie, final asset/video approval en publish approval blijven afzonderlijke expliciete Nitin-events.

## Parallel werk, duplicaten en herstel
- Eén writer per Resolve-project/kandidaat. Andere agents reviewen immutable exports of vastgepinde code.
- Deduplicatie op task_id + revision + inputidentiteit; controleer bestaande ontvangst, actieve uitvoering en resultaat vóór dispatch.
- Een stille agent wordt niet automatisch vervangen. Controleer de bestaande sessie en uitvoerder; bij onzekerheid BLOCKED/UNKNOWN, geen tweede builder.
- Elk defect krijgt defect_id, severity, exact artifact-SHA, tijdcode/framebereik, waarneming, verwacht gedrag en acceptatiecheck.
- Claude herstelt uitsluitend bewezen in-scope defecten zonder nieuwe creatieve richting te kiezen. Behoud voorgangers; gewijzigde bestanden krijgen een nieuwe identiteit en nieuwe toepasselijke QC.
- Respecteer het bestaande werkpakketbudget. Bij herhaalde mislukking eerst oorzaak/ontbrekende capability vaststellen; geen eindeloze ongerichte renders.
- Geen AI mag acceptatiecriteria verzwakken om PASS te krijgen.

## Review en conflicten
- Work/Codex verifieert technische uitvoering; Gemini beoordeelt daadwerkelijke media. Benoem code-inspectie, contactbladen, volledige bewegende review en decode afzonderlijk.
- Metadata en succesvolle decode bewijzen geen volledige grading of juiste captioncompositie.
- Een technisch PASS is geen premium-oordeel; AI-voorkeur is geen Nitin-selectie.
- Conflicterende reviews blokkeren alleen de betreffende kandidaat. ChatGPT formuleert een gerichte hercontrole op exact hetzelfde bestand; geen gemiddelden over kritieke fouten.
- Geen gekalibreerde HDR-goedkeuring of sample-nauwkeurige lipsync claimen vanuit browserreview.
- Nitin ontvangt één gebundeld resultaat met geldige links, bevestigde checks, open punten, aanbeveling en concrete keuze. Geen routinematige interne technische fouten doorschuiven als creatieve keuze.

## State en communicatie naar Nitin
- Persistente resultaten via de bestaande append-only ledger/reducer-procedure; geen directe Master State-edit.
- Rapporteer elke betekenisvolle overgang of blocker met laatste bewezen uitvoeringsmoment. Vermeld wanneer de informatie alleen uit repositorybewijs komt.
- Benoem afzonderlijk: geconfigureerd, bereikbaar, ontvangen, gestart, gebouwd en gecontroleerd.
- Wachtende human gates blokkeren geen onafhankelijke READY-taken.
- Ontbrekende bevoegdheid/toegang wordt concreet benoemd; geen verzonnen ontvangst, uitvoering of voortgang.

## Eerste acceptatieproef
Gebruik de bestaande premium-captionfout in een geïsoleerde kopie:
1. Verifieer concrete Claude-client, native Resolve-verbinding, project/timeline en bronnen.
2. Bied één SHA-gebonden opdracht aan; leg werkelijk ACK en start vast.
3. Claude verschuift de openingstekst tot na het kettinglogo, controleert import/actieve Fusion-compositie en leest exacte instellingen terug.
4. Claude rendert uitsluitend de noodzakelijke korte proef en bewaart outputidentiteit/evidence.
5. Work/Codex controleert technisch; Gemini beoordeelt het exacte bewegende bestand in de bestaande context.
6. Registreer resultaat of gerichte herstelopdracht. Geen creatieve kleur-/captionselectie namens Nitin.
7. Bewijs automatisch oppakken apart: een nieuwe geautoriseerde opdracht wordt zonder handmatige relay eenmaal uitgevoerd. Een handmatig gestarte verbindingstest bewijst geen autostart.

## Activering en onveranderde gates
Dit document is opgeslagen, maar Claude/Gemini-ontvangst, lokale native handshake en end-to-end-autostart zijn nog NIET bevestigd.
De bestaande heartbeatwijziging blijft afzonderlijk NITIN_CHANGE_APPROVAL vereisen. Deze werkafspraak verleent die goedkeuring niet.
PRODUCTION_DEPLOYMENT_AUTHORIZED = FALSE
PUBLICATION_AUTHORIZED = FALSE
FIRST_REAL_POSTER = PAUSED_BY_NITIN
Behoud gelockte master/audio. Geen nieuwe aankopen, Make-activering of publicatie.

## Referenties
- p0e4/evidence/premium_qc_research_v01/EXECUTION_START_AND_LOCAL_REQUEST_V01.json (historische rolverdeling; voor nieuwe Resolve-buildopdrachten geldt bovenstaande beperkte rolcorrectie)
- p0e4/evidence/premium_qc_research_v01_execution/INDEPENDENT_REVIEW_BUNDLE_V01.json
- p0e4/evidence/daily_master_audit_20260930/DAILY_CHECKPOINT.json
- p0e4/MASTER_STATE_LATEST.json
- p0e4/tasks/README.md (taak-inbox die dit werkpakket- en berichtcontract toepast; geen kopie en geen vervanging)
