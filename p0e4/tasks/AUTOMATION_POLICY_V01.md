# Gedelegeerde automatische taakroute — V01

## Autoriteit en rollen

Nitin vraagt in de Work/Codex-sessie van 2026-09-30 om repo-PR → merge → lokale
Claude Code → repo-resultaat, zonder handmatige AI-naar-AI berichten. Zijn aanvulling
is letterlijk: **“punt 2 mag ook automatisch door jouw/codex gedaan worden”**.
Deze delegatie staat ChatGPT/Codex toe begrensde taken en resultaat-PR's te mergen.
De merge is dus gedelegeerde uitvoeringsautorisatie, **geen onafhankelijke menselijke
controle**. Nergens wordt daarvoor `NITIN_APPROVAL=true` geschreven.

ChatGPT specificeert en prioriteert taken. Claude maakt de uitvoering/voorstellen.
Een afzonderlijke lokale Codex-sessie analyseert ieder succesvol Claude-resultaat.
Gemini blijft creatieve/platform-QC in de bestaande context; deze runner koppelt
Gemini niet en verzint geen ontvangst. Nitin houdt creatieve selectie, final approval,
rechtenuitbreiding en publicatie-/productiegates.

## Toegestane eerste versie

| Type | Effect |
|---|---|
| READ_ONLY | Analyse van volledig aangeleverde, SHA-gebonden repo-inputs; geen Claude-bestands-/shelltools |
| BUILD_PROPOSAL | Claude levert codevoorstellen als tekst in het resultaat; de runner past ze niet toe en voert ze niet uit |
| RESOLVE_READ_ONLY | Alleen `get_resolve_status` en het bestaande vastgepinde identiteitsscript; geen Resolve-start |

Een automatische **live Resolve-build is nog niet mogelijk** met de huidige rechten.
Render, Import/Export, projectmutatie, Make, deployment, publicatie, aankopen,
zelfmodificatie, nieuwe MCP-servers en nieuwe taken vanuit modeluitvoer zijn uitgesloten.
De runner schrijft uitsluitend zijn eigen resultaat naar
`p0e4/evidence/task_runs/pr_<nummer>/RESULT.json` via een aparte resultaat-PR.
Codevoorstellen worden pas broncode in een afzonderlijk beoordeelde PR.

De drie bestaande gates blijven FALSE, FALSE en PAUSED_BY_NITIN. De runner schrijft
geen Master State en gebruikt geen reducer-event om een productieclaim te maken.
De bestaande Codex controller/READY seeds en heartbeat worden niet gewijzigd.

## Taakcontract en mergecontrole

Gebruik `AUTOMATED_TASK_TEMPLATE_V01.json`. Maak **één nieuw READY JSON-bestand per
PR**, uitsluitend `p0e4/tasks/inbox/<TASK_ID>_R<revision>.json`. Vul base_commit,
doel, concrete criteria en inputhashes in. Het voorbeeld is DRAFT en niet uitvoerbaar.
Alleen dezelfde repository, de vaste doelbranch en een merge door de lokaal vastgelegde
owner-identiteit worden geaccepteerd. GitHub toont bij gedelegeerde connectoracties de
accountidentiteit; dat bewijst niet welke AI klikte. Bewaar dus taakdoel en review in Git.

Voor auto-merge controleert ChatGPT/Codex het exacte PR-head, het volledige diff,
het schema, de inputs en of scope/criteria binnen deze policy vallen. Gebruik expected
head SHA; geen force-merge, branchbescherming omzeilen of workflow uitvoeren uit de taak.
De lokale runner controleert deze grenzen opnieuw. Hij mergen geen willekeurige taak-PR's;
ChatGPT/Codex doen dat vanuit hun geautoriseerde sessie/koppeling.

Runtime, governance, instellingen, hashpoort en Master State zijn lokaal gepind.
Drift op de actuele doelbranch stopt de verwerking; een wijziging aan die pinnen vraagt
een nieuwe gecontroleerde installatie. Een oude merge met inmiddels gewijzigde/verwijderde
taak wordt geblokkeerd. Historische V01 handmatige packages worden niet uitgevoerd.

## Uitvoering, bewijs en herstel

- launchd controleert elke 180 seconden als de Mac ingelogd en wakker is. Geen polling
  tijdens slaap, geen gegarandeerde start binnen drie minuten bij netwerk-/authproblemen.
- Eigen servicecheckout, vaste lokale runtime, één proceslock, persistente taak/revisiebinding.
  Installatie weigert bij herkenbare bestaande UNCHAINED/P0E4 LaunchAgents; inspecteer
  zulke services voordat er een tweede scheduler ontstaat. Dit detecteert niet alle
  willekeurig benoemde handmatige processen.
- Maximaal één modelpoging per taak/revisie; Claude maximaal 8 turns/300 seconden;
  Codex-review maximaal 300 seconden. Geen betaald API-account of nieuwe credentials
  aangemaakt. Bestaande abonnementen/limieten blijven van toepassing; dit is geen eurocap.
- Intent wordt vóór de modelstart duurzaam opgeslagen. Een crash met onzekere uitvoering
  wordt HOLD, nooit automatisch opnieuw gestart. Nieuwe poging vergt een nieuwe expliciete
  taakrevisie nadat de vorige sessie is onderzocht.
- Lokale ruwe CLI-uitvoer en PID/argv blijven beschikbaar met beperkte bestandsrechten;
  alleen resultaat, review, sessie-ID en hashes gaan naar GitHub. Secretpatronen blokkeren
  bekende tokenvormen; dit is geen volledige garantie dat vrije tekst geen geheim bevat.
- Resultaat-PR is deterministisch, zonder force-push en met exact-head merge. Alleen
  aflevering mag automatisch opnieuw proberen; Claude/Codex worden daarbij niet herstart.
- Codex rapporteert VERIFIED / FAILED / NIET BEWEZEN per criterium. Een modelantwoord
  is geen bewijs van uitgevoerde tests. Resultaat blijft IN_REVIEW; de runner kent nooit
  eigenstandig productieacceptatie of human approval toe. Geblokkeerde taken worden ook
  als bewijs afgeleverd. Bij afleverproblemen blijft lokaal delivery_hold.json staan.

ChatGPT is niet permanent actief door deze installatie. De lokale Codex-review sluit
de automatische terugkoppeling naar de repo; ChatGPT leest die bij de volgende sessie.
Een altijd actieve orchestrator die zelf nieuwe werkpakketten ontwerpt is niet inbegrepen.

## Eenmalige Mac-installatie en acceptatie

De bestanden in Git bewijzen geen lokale activering. Vereist: aangemelde Claude Code,
werkende Codex-login, GitHub CLI `gh` met owner-toegang en bestaande lokale checkout.
Gebruik op de Mac de actuele, schone, gemergde doelbranch en voer vanuit die map uit:

```sh
python3 p0e4/task_runner/install.py --repo "$PWD" --activate
```

De installer controleert bronidentiteit, GitHub-owner, Claude-auth en conflicterende
LaunchAgents; hij installeert onder `~/Library/Application Support/UnchainedTaskRunner/`.
Hij meldt **INSTALLED_ACTIVATED_UNPROVEN**, nooit READY op grond van alleen bootstrap.
Ontbrekende login/trust wordt niet automatisch aangepast of omzeild.
Installatie zonder `--activate` maakt de plist maar start hem niet.

Status: `state/health.json`, per taak `state/pr_<nummer>/`, launchd-label
`com.unchained.claude-task-inbox`. Lokaal pauzeren zonder bestanden te verwijderen:

```sh
launchctl bootout "gui/$(id -u)/com.unchained.claude-task-inbox"
```

Voor lokale acceptatie: eerst één onschuldige READ_ONLY-taak-PR, dan één
RESOLVE_READ_ONLY-taak. Controleer werkelijke argv, beide sessies, toolrechten,
geweigerde ongeldige probe, resultaat-PR, een tweede poll zonder herstart en crash/HOLD.
Controleer ook dat globale/managed Claude-config de sessie niet uitbreidt en dat de
lokale Codex read-only sandbox actief is. Tot dit Mac-bewijs bestaat blijft transport
**NIET BEWEZEN**. Offline tests gebruiken uitsluitend nagebootste modellen en GitHub.

## Bronnen voor CLI-vorm

Officiële Claude Code-documentatie, geraadpleegd 2026-09-30:
https://code.claude.com/docs/en/cli-reference en https://code.claude.com/docs/en/headless.
`--tools ""` beperkt ingebouwde tools; MCP wordt afzonderlijk begrensd met strict config,
de bestaande denies en een aanvullende deny-by-default PreToolUse-poort.
