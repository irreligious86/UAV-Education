# Czech (`cs`) terminology research

Research behind `i18n/cs/terms.md`, done 2026-11-14. Nothing here is binding; the guide is.

## How the sources were read

- Repositories were inspected with a blobless `git clone` and `git ls-tree`; the EdgeTX Czech file was
  downloaded raw and grepped directly.
- Every web page and PDF was read through a fetch tool that returns a model-written extract of the page,
  not the raw text. Quotes in this file are the fragments that extract returned. They are good evidence
  that a term is used in a source, weaker evidence for exact wording, and no evidence of how often a term
  is used. A native reviewer should still read the guide.
- "Confirmed" in the guide means: the chosen Czech term was seen in at least one Czech source listed
  below. 114 table rows; in 103 the chosen term is confirmed, in 11 the chosen term (or one part of the
  row) is not. Six further rows are confirmed but name a rejected variant as unconfirmed.

## Findings that change the brief

1. **No Czech locale exists in any of the four ground tools.** Betaflight Configurator `locales/` has
   ar, ca, da, de, en, es, eu, fr, gl, he, it, ja, ka, kk, ko, nl, pl, pt, pt-BR, ru, sr, sr-Cyrl, uk, uz,
   zh-CN, zh-TW (the URL `locales/cs/messages.json` returns 404). INAV Configurator has bg, de, en, ja, ru,
   uk, zh_CN. QGroundControl `translations/` has no `cs_CZ`. Mission Planner has no `.cs.resx` (there is a
   single `.sk.resx`). Consequence: Czech pilots use these programs in English, so on-screen labels must
   stay English in the translation, and there is no vendor glossary to follow.
2. **The only firmware-side Czech UI found is EdgeTX** (`radio/src/translations/i18n/cz.h`). It supplies
   plyn, letový režim, přijímač, vysílač, baterie, napětí, proud, výkon, telemetrie, kalibrace, failsafe
   (kept English), spínač, trim, mixer.
3. **The textbook skripta.ssps.cz «Vývoj a stavba dronů» could not be read.** Search returns only its
   PDF export URLs, which the fetch tool delivers as binary; the HTML book URL was not reachable. It is
   the most relevant single source and is not reflected in the guide.
4. **Czech Wikipedia was mostly unreachable** (Bezpilotní letadlo, Kvadrokoptéra, Lithium-polymerový
   akumulátor, Samokřídlo, Vrtulník failed; Multikoptéra, Kalmanův filtr were never reached). Read: PID
   regulátor, Regulace (technika), Křidélka, Vrtule.

## Decisions that were not obvious

### Form of address: vykání
- Source uses «ты»; uk keeps «ти», en has only "you".
- Every Czech FPV or hardware text opened uses vykání with plural imperatives: Rotorama «Nastavení
  Betaflight» („stáhněte“, „nastavte“, „Vždy nastavujte bez vrtulí“), «První let» („Zkontrolujte…“,
  „Nebojte se ptát“), «RC vysílačky», «Nářadí», the SP Racing F3 manual, the Pilotix F405 manual, Fluke.
  They mix in inclusive first person plural („si projdeme“, „připojíme“). The ČVUT regulator text uses
  only „my“. Tykání was found only in a consumer learning app's store text (Mimo: „Získej…“, „Začni…“).
- Choice: vykání, lowercase, inclusive „my“ allowed. In Czech, tykání to an unknown adult reads as
  marketing or youth register, and no text in this domain uses it. The source's directness survives in
  the imperatives.
- Cost: interface strings with «твой/ты» become „váš/vy“. Still open for a native reviewer (see below).

### Numbers and units
- Czech sources write a decimal comma („~3,8 V/článek“, Rotorama) and a spaced percent („70–80 %“).
- Choice: keep the source's digits and decimal point untouched (they are also code, parameters and
  graded answers); take only the Czech spacing of units and percent in prose.

### крен / тангаж / рыскание
| variant | sources |
|---|---|
| klonění / klopení / zatáčení | Kment (ČVUT 2014, maps roll, pitch, yaw to exactly these); Denk (VUT 2016: klonění, zatáčení); Wikipedia «Křidélka» (klonění, klonivě-zatáčivý moment); Bukovský (ČVUT 2017: „v ose klopení (pitch)“); Červenka (VUT 2016: klonění a klopení) |
| náklon / sklon / zatočení | Nejedlý (VUT 2015) |
| náklon / sklon / kurz or směr | Červenka (in equations), Kašpar (ČVUT 2023) |
| roll / pitch / yaw untranslated | Rotorama («Nastavení Betaflight», «RC vysílačky»: „plyn a yaw na levé páce, pitch a roll na pravé“), Hlinomaz (ZČU 2022) |
| bočení | not found in any source opened |

Choice: English on sticks, axes and logs (what practitioners write); klonění / klopení / zatáčení for the
physical motion. *bočení* is excluded because it could not be confirmed.

### висение
*vis* („ve visu“) in Rotorama, Hlinomaz and Nejedlý. Červenka writes „levitace“. *visení* was not found
anywhere, so the guide uses *vis*.

### полётный контроллер
| variant | sources |
|---|---|
| řídicí / řídící jednotka | Rotorama, Pilotix manual, Červenka, Bukovský |
| letová řídící jednotka | Hlinomaz (glossary entry for FC) |
| letový kontrolér | SP Racing F3 manual |
| letový řadič, řadič | Pilotix manual, Nejedlý |
| stabilizační jednotka | Denk |
| letový ovladač | machine-translated Radiolink manual (discarded as a source) |

Choice: *řídicí jednotka (FC)*, with the codified spelling *řídicí*; most sources write *řídící*.
EASA's Czech AMC uses „dálkově řídicí stanice“ for the pilot's station, which is a different thing.

### аккумулятор
*baterie*: EdgeTX, Rotorama (three pages), Pilotix manual, EASA AMC, Hlinomaz („Lithium-polymerové
baterie“). *akumulátor*: Červenka, Nejedlý, Bukovský, Denk, once in Rotorama «Nářadí». Choice: *baterie*
as the default, *akumulátor* allowed where the type is the topic. Cell is *článek* everywhere.

### пульт
*vysílačka* (Rotorama, three pages), *RC vysílač / vysílač* (Červenka, EdgeTX, SP F3 manual, Hlinomaz),
*rádio* (Rotorama «RC vysílačky», EdgeTX „data vysílače“ vs „Nečinnost rádia“), *ovladač* (Nejedlý).
Choice: *vysílačka* for the handheld, *vysílač* for the transmitting side of a link.

### регулятор (ESC)
*regulátor otáček* (Bukovský, Hlinomaz „elektronický regulátor otáček motoru“, Nejedlý), *regulátor*
(Rotorama, SP F3 manual), *regulátor motoru* (Červenka), ESC (Pilotix manual). *regulátor* is also the
standard word for a controller in control theory (Wikipedia, ČVUT, ZČU), hence the rule to say ESC in
control modules.

### БПЛА / БАС
EU 2019/947 defines *bezpilotní systém (UAS)* and uses *bezpilotní letadlo*. Theses prefer *bezpilotní
letoun* (Červenka, Kovář, Kment) or *bezpilotní létající prostředek* (cited in Bukovský). *letoun* in
Czech aviation is a fixed-wing aeroplane, so the guide takes the legal term and keeps the abbreviation UAV.

### прошивка, арминг, failsafe, throttle
- *firmware* is never translated (Rotorama, SP F3 manual, three theses).
- *armovat / armování* is the Czechised form (Rotorama); disarm stays English („v poloze disarm“). No
  Czech verb for disarm was found.
- *failsafe* stays English (EdgeTX „Nastavit failsafe“, Rotorama).
- *plyn* everywhere (EdgeTX „Plyn“, „Páka plynu“; Rotorama; Červenka; Hlinomaz). Nejedlý's „ovládání tahu“
  is an outlier.

### Control theory
- setpoint: *žádaná hodnota* (Wikipedia PID, ČVUT) vs *požadovaná hodnota* (Nejedlý, Wikipedia Regulace,
  ZČU) vs "setpoint" (Hlinomaz). Chosen: *žádaná hodnota (setpoint)*.
- overshoot: *překmit* (Wikipedia, ČVUT, Nejedlý) vs *přeregulování* (ZČU textbook). Chosen: *překmit*.
- controller output: *akční zásah* (Nejedlý), *akční veličina* (Wikipedia), *akční člen* = actuator (ZČU).
- margins: the ZČU textbook says *bezpečnost ve fázi / v zesílení*. The brief's *fázová bezpečnost* was
  not seen in a source that opened; it is listed as an unconfirmed variant.
- tuning: *ladění / naladění* (Hlinomaz, ČVUT) vs *nastavení* (ČVUT heading „Jak nastavit a odladit“).
- disturbance and fault are both *porucha* (Wikipedia PID, ZČU vs EASA AMC, Pánek). Kept, with a warning.

### State estimation
*odhad stavu*, *rozšířený Kalmanův filtr*, *šum měření*, *kovarianční matice* in Mráz (ZČU 2012) and
Kašpar (ČVUT 2023). Process noise: *procesní šum* (Kašpar) vs *šum systému* (Mráz); chosen the former.
bias and drift stay English (Kašpar glosses bias as „konstantní odchylka“).

### Course vocabulary (weakest area)
- track → *okruh*, path → *cesta*: neither was found in a source. Mimo's Czech store text says „učicí
  trasy“ for learning paths. uk kept «трек»; Czech has no such loanword in this sense.
- quiz → *kvíz*: only one source („testy a kvízy“); Czech Moodle material says *test*.
- сдан → *splněno* (Moodle „splnění“), exam *složeno* (EASA „složení zkoušky“), project *odevzdáno*
  (Moodle „odevzdání úkolu“). освоен → *zvládnuto* and пройден → *dokončeno* are my choices, unconfirmed.
- справочник, журнал фейлов, задача с числовым ответом, итоговый проект, лабораторная, источники: plain
  Czech renderings, not seen in a source.

### Diagnostics markers
Czech manuals label troubleshooting tables „Příznak / Možná příčina / Řešení“ (Hyundai) or „Popis
poruchy / Možná příčina / Odstranění příčiny“ (Blum). Chosen: `**Příznak:**`, `Možná příčina:`,
`Co udělat:` (mirrors the source's «Что сделать» and survives the variants „Co zkontrolovat/udělat“),
`V logu:` / `Co je vidět v logu:`, `Důsledky:`. „Důsledky“ and „Co udělat“ are ordinary Czech but were
not seen as table labels. Parser prefixes are listed in the guide; note `FIELD_KEYS` matches with
`startswith` on the lowercased line, so „v logu“ also covers „V logu/na přístroji:“.

## Open questions

1. Vykání or tykání: a Czech reader of the target age should confirm. If the course wants the Mimo-style
   register, only the style rule and the interface strings change; the term table does not.
2. *okruh* / *cesta* for track / path, *zvládnuto* for «освоен», *příručka* for «Справочник».
3. *kvíz* or *test* for «квиз».
4. Is *bočení* used by Czech multicopter pilots for yaw? Not found, but the main Wikipedia articles and
   the SSPŠ textbook were unreadable.
5. *baterie* vs *akumulátor* as the default: sources split by register (practice vs theses).
6. A Czech verb for disarm, and whether *vis* needs the gloss „(hover)“ at first mention.
7. Whether dron.caa.gov.cz wording differs from the regulation text; the ÚCL site itself was not reached
   (only its hosted EASA AMC translation).
8. Unit for rotational speed if the source ever spells out «об/мин»: Czech *ot/min* was not confirmed.

## Sources read (tag = key used in the guide)

| tag | source | URL |
|---|---|---|
| EdgeTX | EdgeTX Czech UI strings | https://raw.githubusercontent.com/EdgeTX/edgetx/main/radio/src/translations/i18n/cz.h |
| Rot-BF | Rotorama, «Nastavení Betaflight» | https://www.rotorama.com/t-nastaveni-betaflight |
| Rot-1st | Rotorama, «První let» | https://www.rotorama.com/t-prvni-let |
| Rot-TX | Rotorama, «RC vysílačky» | https://rotorama.com/t-vysilacka |
| Rot-tools | Rotorama, «Nářadí, nástroje a pomůcky» | https://rotorama.com/t-naradi-nastroje-a-pomucky |
| SPF3 | SP Racing F3 manual (Rotorama) | https://www.rotorama.cz/assets/docs/c456e34c784995da7b7befec670e6622/903-1/spracingf3-navod_58735bed2f7cc.pdf |
| Pilotix | Pilotix FC F405 V3 manual CZ | https://public.hobbydrone.cz/Pilotix/5447/Manual/Pilotix%20FC%20F405%20V3%20ICM42688%20%28SKU%205447%29%20manual%20CZ.pdf |
| EU947 | Regulation (EU) 2019/947, Czech text | https://ceet.vsb.cz/export/sites/ceet/cnt/droneexpert/cs/pravni-predpisy/PROVADECI-NARIZENI-KOMISE-EU-2019-947.pdf |
| AMC | EASA AMC/GM to 2019/947, Czech (ÚCL), first 100k characters | https://www.caa.cz/wp-content/uploads/2021/01/Decision_ED_2019_021_RAnnexes_CS.pdf |
| Quiz | A1/A3 exam question bank in Czech | https://quizvds.it/cs-cz/pdf/drony-a1-a3 |
| epravo | epravo.cz, «Drony v praxi» | https://www.epravo.cz/top/clanky/drony-v-praxi-kde-konci-hracka-a-zacina-pravni-odpovednost-120326.html?pdf=1 |
| Červenka | O. Červenka, Systém řízení letových charakteristik autonomního dronu, VUT FIT 2016 | https://www.fit.vut.cz/study/thesis-file/18993/18993.pdf |
| Nejedlý | J. Nejedlý, Řízení stability kvadrokoptéry, VUT FIT 2015 | https://www.fit.vut.cz/study/thesis-file/16938/16938.pdf |
| Denk | F. Denk, Automatické udržování letu RC modelu, VUT FIT 2016 | https://www.fit.vut.cz/study/thesis-file/18283/18283.pdf |
| Hlinomaz | V. Hlinomaz, Návrh dronu, ZČU FEL 2022 | https://otik.uk.zcu.cz/bitstream/11025/48931/1/Bakalarska%20prace%20Hlinomaz.pdf |
| Kovář | J. Kovář, Analýza přístupů k autonomnímu přistání dronu na plošině, ZČU FAV 2023 | https://dspace5old.zcu.cz/bitstream/11025/55118/1/Analyza%20pristupu%20k%20autonomnimu%20pristani%20dronu%20na%20plosine.pdf |
| Mráz | J. Mráz, diploma thesis on nonlinear filters, ZČU FAV 2012 | https://otik.uk.zcu.cz/bitstream/11025/2649/1/DP-Mraz.pdf |
| Kment | J. Kment, Návrh pokročilých systémů řízení pro malý RC letoun, ČVUT FEL 2014 | https://dspace.cvut.cz/bitstream/handle/10467/61162/F3-DP-2015-Kment-Jan-DP_KmentJan_bez_p.pdf |
| Bukovský | D. Bukovský, Kolmo startující UAV samokřídlo, ČVUT FEL 2017 | https://dspace.cvut.cz/bitstream/handle/10467/68551/F3-BP-2017-Bukovsky-Daniel-bcth-buk-final.pdf |
| Kašpar | J. Kašpar, Algoritmy pro palubní odhadování pohybových stavů vozidla, ČVUT FEL 2023 | https://dspace.cvut.cz/bitstream/handle/10467/109394/F3-BP-2023-Kaspar-Jakub-Algoritmy_pro_palubni_odhadovani_pohybovych_stavu_vozidla_pomoci_multisenzoricke_fuze.pdf |
| ZČU-LS2 | ZČU KKY, Lineární systémy 2, učební texty 2011 (first 100k characters) | https://kky-sw.zcu.cz/uploads/courses/ls2/LS2_Ucebni_texty_2011.pdf |
| ČVUT-reg | ČVUT FEL Robosoutěž, regulators text | https://robosoutez.fel.cvut.cz/sites/default/files/souboryredakce/regulatory2.pdf |
| Pánek | R. Pánek, Systémy odolné proti poruchám, VUT FIT, PAD 2017 | https://fit.vut.cz/research/publication-file/c144458/279770/PAD_2017_panek.pdf |
| Wiki-PID | cs.wikipedia, PID regulátor | https://cs.wikipedia.org/wiki/PID_regul%C3%A1tor |
| Wiki-Reg | cs.wikipedia, Regulace (technika) | https://cs.wikipedia.org/wiki/Regulace_(technika) |
| Wiki-Křid | cs.wikipedia, Křidélka | https://cs.wikipedia.org/wiki/K%C5%99id%C3%A9lka |
| Wiki-Vrtule | cs.wikipedia, Vrtule | https://cs.wikipedia.org/wiki/Vrtule |
| Fluke | Fluke CZ, «Co je to Ohmův zákon?» | https://fluke.com/cs-cz/dalsi-informace/blog/elektricke/co-je-to-ohmuv-zakon |
| Hyundai | Hyundai infotainment manual, «Řešení problémů» | https://ownersmanual.hyundai.com/ivi/STD_GEN5/AVNT/EUR/Czech/012_Appendix_1.html |
| Blum | Blum, «Návod k odstranění poruch» | https://www.blum.com/cz/cs/landingpages/products/servo-drive/troubleshooting/ |
| Moodlista | VŠB, Moodlista autor, 2nd ed. | https://fbiweb.vsb.cz/~sen76/data/uploads/skripta/moodlista-autor-2.-vydani.pdf |
| CUNI-Moodle | Charles University, «Sledování plnění» | https://dl.cuni.cz/wp-content/uploads/Návod-Sledování-plnění.pdf |
| Mimo | Mimo app, Czech App Store text | https://apps.apple.com/cz/app/mimo-learn-coding-code-app/id1133960732?l=cs |

Repositories checked for a Czech locale (none found): betaflight/betaflight-configurator,
iNavFlight/inav-configurator, mavlink/qgroundcontrol, ArduPilot/MissionPlanner.

## Sources that could not be read

- skripta.ssps.cz «Vývoj a stavba dronů»: `/books/vyvoj-a-stavba-dronu/export/pdf` and two page exports
  came back as binary; `https://skripta.ssps.cz/` and the book's HTML URL were not reachable.
- cs.wikipedia.org: Bezpilotní letadlo, Kvadrokoptéra, Lithium-polymerový akumulátor, Samokřídlo, Vrtulník
  (fetch failed); Multikoptéra, Kalmanův filtr, Dron (blocked before the request).
- caa.gov.cz / dron.caa.gov.cz pages (blocked); `caa.cz/.../5-Letove-zasady-–-letoun.pdf` (client error);
  the Ministry of Transport UAS leaflet on md.gov.cz (captcha).
- theses.cz PDFs (19157, Medla 2018, STAG95180), is.muni.cz, is.vstecb.cz: bot-check page instead of the
  document. dspace.vut.cz: access denied. ČVUT Brož 2016 and the record 10467/68636: server error.
- Discarded as evidence: cs.manuals.plus Radiolink Pixhawk page (machine translation);
  rotorama.com `t-ridici-jednotky` and `t-legislativa` (served in English).
