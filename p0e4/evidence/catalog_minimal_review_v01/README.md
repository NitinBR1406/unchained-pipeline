> Update: 67 expliciete readiness-antwoorden uit Nitin batch 1–5 + mashups zijn verwerkt. De uitgeschreven regels geven 36 muziek+zang-gereed en 31 zang-pending. Dit wijkt af van de verwachte controletotalen; reconciliatie met Nitin staat open. Zie NITIN_BATCH_REVIEW_REPORT_V01.md en BATCH_SEMANTIC_VALIDATION_RECEIPT.json. Geen eerdere antwoorden opnieuw nodig.

# NITIN_MINIMAL_SEMANTIC_REVIEW_V01

Begin in het HTML-reviewformulier bij het aparte **NITIN 2008**-blok. Er zijn acht kinderen: asma, KHAN KHAN, KHILTA GHUL, khud se, raeena, SANIYA, tum sabse en ye raat (zie de exacte bestandsnamen in het formulier). Nitin heeft alle acht identiteiten expliciet bevestigd als zijn bestaande originals uit circa 2008 binnen het Vatsal recreation-pakket. identity_confirmed=YES, TYPE=ORIGINAL_RECREATION, NEXT_ACTION=REVIEW_WITH_VATSAL en ACTION_OWNER=NITIN_AND_VATSAL zijn ingevuld. Gereedheid en prioriteit blijven UNKNOWN.

## Wat is verminderd?

De 88 oorspronkelijke kandidaten zijn volledig verantwoord in REVIEW_REDUCTION_AUDIT.json:

- **63 duidelijke songgerichte mappen**: 59 top-level mappen en vier oudere child-songmappen. De technische groepering staat vast; identiteit, TYPE en gereedheid zijn niet automatisch bewezen.
- **8 NITIN 2008-kinderen**, apart reviewblok.
- **4 mashup-/medleybenamingen**, apart blok; TYPE niet uit de naam ingevuld.
- **2 ambigue items**: Intro beat mogelijk bij Khairiyat; oudere Chunar mogelijk een versie van Chunar 2025. Eerst identiteit, pas daarna eventueel afzonderlijke gereedheid.
- **11 downloadkandidaten uit de gereedheidsreview gehaald**: vier gemengde containers, zes mogelijke bestaande-songmediafolders en één werk-/administratiemap (Stater). De ene muziekfile in Stater blijft apart bewaard in de audit; de parent wordt geen song.

De oorspronkelijke minimale review bevat **75 directe semantische regels en 2 voorwaardelijke identiteitsregels**. Inmiddels zijn 67 readiness-antwoorden ingevuld; de historische Chunar-versie blijft expliciet afzonderlijk. Verder terugbrengen zou onbewezen songidentiteiten of gereedheid aannemen. Dit is geen claim dat 75 unieke songs zijn vastgesteld. Batchantwoorden voor expliciet geselecteerde regels verminderen invoer; UNKNOWN mag blijven staan. Zes bestaande containers en 19 bestaande uitsluitingen blijven buiten songgereedheid.

## Technische koppelingen en duplicaten

Twee downloads zijn met exacte SHA256-gelijkheid gekoppeld aan een asset in een bestaande songmap: Chand Mera dil en Tujhe ko. Dit koppelt bytes aan een map, niet auteurschap, zangidentiteit of gereedheid. Een derde hashgroep bevat drie gelijke Downloads-bestanden: één representant, twee aliassen, songidentiteit UNKNOWN. Hierdoor blijven van de oorspronkelijke 107 losse mediakandidaten 103 niet-gekoppelde representanten over. Eén admin-ingebed mediarecord blijft daarnaast apart bewaard.

Identieke namen/groottes van de twee Apna-transferbundels zijn geen bytebewijs: cloudbestanden zijn niet gelezen. Bovendien bevatten beide bundels meerdere songs. Geen automatische foldermerge. Vermoedelijke links (HUA MAIN/Hua Mein, phir-mohabbat/Phil Moh, Baarish, Saari Duniya) worden gebundeld ter bevestiging aangeboden. Geen formulier per losse download; die blijven buiten het songcatalogusbesluit tot relevantie/identiteit bekend is.

## Gebruik

HTML: selecteer de bedoelde regels, kies een veld/waarde en pas het toe. Vul desgewenst individueel aan. Download antwoorden als JSON vóór afsluiten; geen automatische opslag of verzending. CSV en JSON zijn alternatieven. Alle tien gevraagde velden zijn aanwezig. Toegestane waarden staan machineleesbaar in allowed_values; TYPE, PRIORITY en ACTION_OWNER zijn dropdowns. ACTION_OWNER betekent actie-uitvoerder, geen rechtenhouder. NEXT_ACTION=OTHER kan met een opmerking worden verduidelijkt.

Onbevestigde semantische velden blijven UNKNOWN. Master V16.3/state29 bevat een exact-SHA final-video-approval voor Aakhri Ishq; die is geen bewijs voor de tien catalogusvelden en is daarom niet als algemene gereedheid overgenomen. De nieuwe expliciete Nitin-bevestiging is afzonderlijk vastgelegd in p0e4/evidence/catalog_semantic_events/NITIN_2008_SEMANTIC_CONFIRMATION_V01.json en deterministisch op precies de acht kinderen toegepast. Historische productie met een andere engineer en Vatsals update-/recreatiescope, inclusief eventuele lyrische revisie, zijn context uit Nitin's verklaring; geen bewijs dat revisie per song nodig is.

Deze projectie gebruikt de gehashte Discovery V02-evidence en de afzonderlijk vastgelegde expliciete Nitin-events. Geen nieuwe iCloud-toegang, cloudhydratie of bronmutatie. Master State en oude discovery blijven ongewijzigd. Geen MASTER_CATALOG_V01 aangemaakt; voorbereiding daarvan wacht op ontvangen Nitin-review. Geen productie- of publicatiemutatie.
