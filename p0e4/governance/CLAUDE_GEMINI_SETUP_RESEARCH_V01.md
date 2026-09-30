# Claude en Gemini inrichting — onderzoek V01
Datum: 2026-09-30, Europe/Amsterdam
Status: RECOMMENDATION_ONLY_NOT_ACTIVATED. Aanvulling op AI_ROLES_AND_COMMUNICATION_V01.md; geen nieuwe runtime, route, kosten of human gate geactiveerd.

## Aanbeveling
Claude Code lokaal op de bestaande Mac is de kandidaat-builder voor Resolve. De native Resolve-integratie is de eerste te testen verbinding. De bestaande controller blijft de regie uitvoeren; voeg geen concurrerende scheduler toe.
Gemini behoudt de bestaande strategiechat. Voor toekomstige autonome media-QC is een afzonderlijke API-worker de kandidaat, met expliciete overdracht vanuit de bestaande context. Die API-route is een voorgestelde architectuurwijziging, geen reeds geautoriseerde vervanging van de verplichte chatroute.

## Bronnenbevindingen
Anthropic documenteert programmatische Claude Code-uitvoering via CLI/SDK en gestructureerde resultaten. Dit ondersteunt een meetbare builder-run. Bare mode slaat onder meer CLAUDE.md, automatisch gevonden MCP-configuratie en abonnementslogin over; pas die niet blind toe. [1]
Lokale MCP-extensions en remote connectors hebben een ander uitvoeringsbereik. Een cloudchat krijgt niet vanzelf toegang tot lokale Resolve. [2]
De Dispatch-documentatie zegt dat nieuwe gebruikers niet meer kunnen instappen en dat bestaande gebruikers voorlopig door kunnen. [3]
De Cowork-documentatie kondigt voor Pro/Max vanaf 6 oktober 2026 clouduitvoering voor nieuwe taken aan. Dezelfde pagina bevat nog oudere lokale instructies. Behandel de lokale Cowork-route daarom als account-/versieafhankelijk, niet als bewezen toekomstvaste builder. [4]
Claude Code heeft eigen lokale Desktop-scheduling; dat is een andere functie dan Cowork-scheduling. [5]
Google documenteert video-upload/verwerking, instelbare sampling en standaard statische videosampling van 1 FPS. Korte fouten kunnen daardoor gemist worden. [6]
JSON-schema-output is beschikbaar, maar correcte structuur bewijst geen juiste beoordeling. [7]
Google AI Studio-abonnementsvoorzieningen en productie-API-billing hebben verschillende grenzen; verifieer het account en budget vóór API-gebruik. [8]

## Voorgestelde Claude-configuratie
- Uitvoering op de bestaande Mac, in de bestaande repositorycontext; één builder per Resolve-project.
- Eerst huidige clientversie, login, beschikbare native MCP-tools, actieve project/timeline en read-only handshake vaststellen.
- Bestaande CLAUDE.md/configuratie inspecteren vóór uitbreiding. Houd instructies kort: rol, autoriteit, verplichte governanceverwijzing, taakcontract, bronselectie, herstel/QC en gates.
- Controller levert een taak op exacte commit/inputhashes. Claude levert ACK, sessie-ID, voortgang, renderjob-ID en exact outputmanifest.
- Voor onbeheerde uitvoering: CLI of Agent SDK beoordelen; SDK pas toevoegen als callbacks/statebeheer dat werkelijk rechtvaardigen.
- Alleen noodzakelijke tools en werkpaden toestaan; geen algemene bypass van permissies. Publicatiegate blijft buiten de builder.
- Gebruik een expliciete sessie-ID per taak, met parent-context naar bestaande Dispatch; nooit blind de laatst gebruikte conversatie hervatten.
- Mac/Resolve-beschikbaarheid en renderstatus worden gecontroleerd vóór claim en vóór retry. Onzekere uitvoering betekent geen tweede render.
- Modelkeuze volgt uit bestaande accounttoegang en een korte benchmark; geen onbewezen kwaliteitsranglijst of nieuw abonnement.

## Voorgestelde Gemini-configuratie
- Strategie/merk/platformadvies blijft in de bestaande chat https://gemini.google.com/app/7c9afdcb27030bcb.
- QC-profiel bevat merkregels, performanceprioriteit, goedgekeurd logo/fonts, referentiebeelden, exacte captiontekst, bekende defectklassen en beperkingen.
- API-worker uitsluitend na route-/kostenbesluit: per review volledige compacte instructies + exact bestand; geen automatische overerving van browserchat, Gem of geheugen aannemen.
- Bestandsidentiteit door de uitvoerder berekenen, aan uploadreceipt koppelen en verwerking gereed afwachten. Gemini laten verklaren dat het een hash heeft geverifieerd is geen bewijs.
- Registreren: model-ID, API-versie, promptrevisie, reviewbestand-SHA, tijdlijnmapping, sampling, resolutie, originele reactie en gevalideerd rapport.
- Rapport: status PASS/FAIL/INCONCLUSIVE, defecten met tijdcodes en ernst, dekking, onzekerheid, voorkeur en beperkingen. Geen approvalvelden namens Nitin.
- Volledige video voor samenhang; hogere sampling en afzonderlijke frames rond captionovergangen en logovensters. Leg bij uitsneden de offset naar de master vast.
- Lokale technische checks blijven nodig: volledige decode, tijdvensters, actieve Fusion-compositie en gradebereik. AI-videoanalyse bewijst geen inspectie van ieder frame of gekalibreerde HDR-kleur.
- Eerste visuele vergelijking zo mogelijk blind met neutrale variantlabels; buildervoorkeur niet vooraf als gewenste uitkomst meesturen.
- Bewaar resultaten in repository en media op Shared Drive. API-opslag is geen vervanging van productieopslag.

## Communicatie en overgang
Taak gereed → concrete Claude ACK → buildmanifest → onafhankelijke technische verificatie en Gemini-QC → gerichte defecten terug naar Claude → één samenvatting aan Nitin.
Bestaande communicatie-/deduplicatieregels blijven gelden. Geen extra autonoom mechanisme naast de bestaande controller activeren.
Een nieuwe Gemini API-review is een zelfstandige run met broncontext; geen verborgen nieuwe strategiechat.
Bestaande Dispatch- en Gemini-context blijven bewaard. Migratie wordt expliciet geregistreerd met ontvangstbewijzen.

## Acceptatie vóór activering
1. Inventariseer feitelijke accounts, clients, MCP-handshake en bestaande controller; geen secrets in evidence.
2. Claude herstelt één bestaande captionfout in een proefkopie, leest instellingen terug en rendert.
3. Verifier/Gemini beoordelen exact die export en tonen dat de fout weg is.
4. Test ook een schoon fragment en bekende fouten op missen en onterecht afkeuren.
5. Meet één volledige taak zonder menselijke relay; opnieuw aanbieden veroorzaakt geen duplicaat.
6. Test herstart/onderbreking: bestaande render identificeren voordat hervatting wordt besloten.
7. Pas daarna activering binnen expliciete scope. Heartbeatwijziging en eventuele betaalde API-inzet blijven afzonderlijke gates.

## Niet vastgesteld
Geen verse Mac-inspectie, geen Claude/Gemini-ontvangst, geen nieuwe API-call, geen live native handshake, geen kostenmeting en geen autonomie-PASS in dit onderzoek. Historisch Resolve 21.1.0.17 is geen actuele probe. Repozoekactie leverde geen voldoende bewijs van een operationele Gemini-API-worker op; dat bewijst niet dat er elders geen bestaat.

## Bronnen
[1] https://code.claude.com/docs/en/headless
[2] https://support.claude.com/en/articles/11725091-when-to-use-desktop-and-web-connectors
[3] https://support.claude.com/en/articles/13947068-assign-tasks-from-anywhere-in-claude-cowork
[4] https://support.claude.com/en/articles/13854387-schedule-recurring-tasks-in-claude-cowork
[5] https://code.claude.com/docs/en/scheduled-tasks
[6] https://ai.google.dev/gemini-api/docs/video-understanding
[7] https://ai.google.dev/gemini-api/docs/structured-output
[8] https://ai.google.dev/gemini-api/docs/google-ai-plans
