# Research notes: Transcarpathian dialect version (`uk-zakarpat`)

Date: 2026-11-14. Scope: background for `i18n/uk-zakarpat/terms.md`, the rule file for rewriting the
reviewed Ukrainian translation (`i18n/uk/`) into the Transcarpathian dialect (fallback `uk`).
Nothing was committed; no module was rewritten; `i18n/languages.json` was not touched.

Method: web search plus page fetches. Every feature and word in the guide is tied to a page that was
actually opened and read during this session. Pages were read through a fetch tool that returns an
extraction of the page, not the raw PDF, so individual spellings (especially stress marks and
transcription diacritics) should be re-checked against the originals before anything is quoted as a
citation. Items I know from general background but could not confirm on an opened page are listed in
section 6, not in the guide.

## 1. Status of the variety (the Rusyn question)

- Ukrainian dialectology classifies it as the Transcarpathian dialect (закарпатський говір, also
  середньозакарпатський / підкарпатський / південнокарпатський) of the Carpathian group of the
  south-western dialect area of Ukrainian (Nimchuk, ESU). An Uzhhorod overview cites Dzendzelivskyi's
  conclusion that it has "not a single specific phonetic or grammatical phenomenon" that would set it
  apart from Ukrainian (Sabadosh & Myholynets 2024).
- Part of the speakers and some scholars treat the same speech as Rusyn, a separate East Slavic
  language. In the UzhNU media-centre piece the linguist Pavlo Chuchka calls it "русинська, або
  руснацька, або українська регіональна жива мова" without settling the matter, and the poet Petro
  Midianka quotes Franko: "діалект чи самостійна мова – найпустіше в світі це питання"; Midianka is
  against artificial codification of a separate standard.
- An opinion piece on Radio Svoboda (O. Havrosh) argues the Ukrainian-dialect position and notes that
  political factors historically mattered more than linguistic ones.
- Decision: the guide states both positions in two sentences, uses the label «Закарпатська говірка
  (експеримент)» and makes no claim. Rusyn codifications (Prešov standard, Kercha's dictionary) were not
  used as sources for forms; I. Kercha's «Словник русинсько-український» could not be opened at all, so
  it was not even used as a cross-check.

## 2. Sources opened and what each contributed

### Core descriptions

| Source | URL | Contribution |
|---|---|---|
| V. V. Nimchuk, «Закарпатський говір», Енциклопедія Сучасної України, vol. 10 (2010) | https://esu.com.ua/article-14618 | Backbone: four groups and their reflexes of *o, *e (кунь / кÿнь / кінь), ы, е→и, case endings, `май`, enclitics `ся, ня, тя, го, ї`, demonstratives `сись, тот, аттот`, `тко/ко`, 1sg `знаву`, contracted `думаш/думат`, 3sg `-т` vs `-ть` by area, 1pl `-ме`, past `ходив-им, ходила-м, ходили-сме`, conditional `бим / бых`, syntax (parataxis, dative possessive, `ги`, `на` + acc.), loan layers (Hungarian, Romanian in the east, Slovak in the west: `кедь, облак, пец`; German: `файный`), bibliography |
| Ukrainian Wikipedia, «Закарпатський говір» | https://uk.wikipedia.org/wiki/Закарпатський_говір | Same content after Nimchuk's article in «Енциклопедія української мови» (2000); adds dative enclitics `ми, ти, му`, past particles `-им/-ем/-ись/-есь`, group names. First attempt to open it was blocked, a later one worked |
| English Wikipedia mirror, Transcarpathian dialect | https://wiki.riteme.site/wiki/Transcarpathian_dialect | Only a small word table: `дараб` (piece), `варош`, `жеб`, `езер`, `вать` (or). Weak source; used as second confirmation only |
| ESU «Гуцульський говір» (N. Khobzei) | https://www.esu.com.ua/pdf/file/25035.pdf | What is Hutsul and must be kept out: `робє, ходє, купʼю`, `бих`, Hutsul lexicon |
| ESU «Лемківський говір» (P. Hrytsenko) | https://www.esu.com.ua/pdf/file/54199.pdf | What is Lemko: future `буду робив`, instrumental `-ом` (`добром жоном`), fixed stress, `ґрулі`, `кукуріца` |
| ESU «Бойківський говір» | https://www.esu.com.ua/pdf/file/36048.pdf | Opened by mistake (wrong id); confirms Boyko has the analytic past/conditional forms too |

### Uzhhorod school papers (Науковий вісник УжНУ, серія Філологія, and UzhNU repository)

| Source | URL | Contribution |
|---|---|---|
| A. Halas, «Діалектна специфіка фраземіки боржавської говірки Закарпаття» (2020) | https://dspace.uzhnu.edu.ua/jspui/bitstream/lib/34927/1/… (ДІАЛЕКТНА СПЕЦИФІКА.pdf) | Borzhava villages (Irshava district): `ÿ` reflex, `ы`, `типір`, `вирьх`, instr. `-ôў`, loc. pl. `-ох`, short adjectives (`годен`), free `ся`; words `відіти, перст, тайстра, дяка, ларма, чилядь, кал, куртый, горі, долу, ниґда, пиля, метати, густи, тямка` |
| H. Vovchenko, «Синтаксис народного мовлення в діалектному словнику» (2018) | https://dspace.uzhnu.edu.ua/jspui/bitstream/lib/22311/1/… (Галина ВОВЧЕНКО (Ужгород).pdf) | Quotes Sabadosh's Sokyrnytsia dictionary (Maramorosh, Khust district): conjunctions `ай, айбо, та, куй, бо, ги/гі, гиби, хуть, вадь/авадь/ци, аж, шчо`; `байловати`; dative `ти` («ги ти кажу»), «Треба ми алаш учинити» |
| I. Sabadosh, «Словотвірний потенціал чужомовних запозичень…» (2021) | https://visnyk-philology.uzhnu.edu.ua/article/download/257661/254501/592900 | Sokyrnytsia: `ґазда, лиґінь, рянда, жеб, тиґла, хосен → хосновитый, фіґля, марга` with Hungarian/German/Romanian etyma |
| I. Sabadosh, «Про лексико-семантичні паралелі подільського і закарпатського говорів» (2023) | https://visnyk-philology.uzhnu.edu.ua/article/download/308800/300345/713346 | Sokyrnytsia: `видіти, упоздити, уповісти, упоминати, бановати, ґанч, удатный, вредный, боржи, ватра, вуйко` |
| O. Myholynets, O. Pyskach, on Nimchuk's Dovhe dictionary materials (2023) | https://visnyk-philology.uzhnu.edu.ua/article/download/308597/300144/712826 | Dovhe (Borzhava): `кидь` (if), `ни` negation, 1pl `идеме`, `видав`, `вонка`, `студено`, `тÿлко`, future with `буде`, free `ся` |
| A. Halas, on Nimchuk's card file and noun inflection (2024) | https://visnyk-philology.uzhnu.edu.ua/article/download/320554/311172/743017 | Dovhe: dat. `-ови`, loc. pl. `-ох`, nom. pl. `-ове`, initial `и`, soft `рь` |
| A. Halas, «Вставні компоненти в закарпатському говірковому мовленні» (2025) | https://visnyk-philology.uzhnu.edu.ua/article/download/349325/336663/810104 | Parentheticals `ачий, видав, никай, чуй, иппен, про вшитко, най`; `так бых дыхав` (central `бых`). OCR was poor and meanings are not given there |
| O. Pyskach, verbs of defective speech (2022) | https://visnyk-philology.uzhnu.edu.ua/article/download/274187/269386/631812 | 32 villages across all four groups: comparatives with `ги / гі / гибы`; `дуже` as the intensifier; `упôвісти` |
| Yu. Yusyp-Yakymovych, on Dzendzelivskyi (2021) | https://visnyk-philology.uzhnu.edu.ua/article/download/257757/254593/593122 | `віл / вул / вÿл`, `ы`, 1pl `рóбиме`, contracted `спíваш`, `-ова-` verbs (`куповати`), perfect `ходивим, ходилисьте`, `днесь`, `тко/ко` |
| M. Medved, on V. Dobosh's works (2024) | https://visnyk-philology.uzhnu.edu.ua/article/download/322166/312720/747100 | Enclitics `-м, -сь, -сьме, -сьте`; prepositions `коло, около, пиля, попри`. Titles only, no examples |
| I. Sabadosh, O. Myholynets, «Наукові здобутки Ужгородської діалектологічної школи» (2024) | https://visnyk-philology.uzhnu.edu.ua/article/download/324987/314985/753624 | Dzendzelivskyi's verdict on the status of the dialect; pointers to Dobosh's syntax and Lyzanets |
| H. Martynova, Middle Dnipro–Transcarpathian parallels (2023) | https://visnyk-philology.uzhnu.edu.ua/article/download/308589/300140/712812 | Phonetics only (soft р', ц', narrowing of е, no prothesis); nothing that can be spelled in the guide |
| V. Putrashyk, dialect words with root -хос(е)н- in the Transcarpathian press (2025) | https://visnyk-philology.uzhnu.edu.ua/article/download/349355/336699/810184 | `хосен` and its family are alive in regional newspapers |
| H. Shkurko, dissertation abstract on transport vocabulary (2021) | https://lnu.edu.ua/wp-content/uploads/2021/11/aref_shkurko.pdf | Confirms the four-group division and `тот`; otherwise not used |

### Loanword studies

| Source | URL | Contribution |
|---|---|---|
| O. Hvozdiak, «Динамічні процеси у складі германізмів українських говірок Закарпаття» (2016) | https://journals.nubip.edu.ua/index.php/Filol/en/article/view/11179/9792 | The richest list for a technical course: `штимовати, пуцовати, луфтовати, шпоровати, вартовати, мутерка, рула, вінкель, васерваґа, цуґ, ґанок` (corridor), `фест` (= strong, firm), `ґанц, фертик, фурт, куртий, фрішний, шіковний, балта, крумплі`; notes which are being displaced and that younger speakers rarely use them |
| Ya. Shetelia, «Німецькі запозичення в українському діалектному мовленні закарпатського ареалу» (2024) | https://lingstud.od.ua/wp-content/uploads/2025/03/39-13.pdf | `друт, цанґлі, цолшток, клямра, діля, ташка, трафити, ріхтувати, дірект, цурюк, капут, проба, пех, луфт, фест, шпоровний, фіртель` |
| D. Toder, S. Toder, Hungarian-origin lexis in the village of Simer (2016) | https://eprints.oa.edu.ua/5701/1/54.pdf | Uzh-valley village: `файта` (family), `варош`, `ґомбічка`, `лампаш`, `коцка`, `біціґля`, `хосен`, `ґазда`, `рянда`, `калап` |
| V. Shylov, dialect elements in the linguistic landscape of Transcarpathia (SlavVaria 2025) | https://journals.lib.pte.hu/index.php/slavvaria/article/download/8333/8223/18459 | Words on real signs: `бовт` («мʼясний бовт»), `варош`, `туй`, `файта`, `хыжа`, `цімбор`, `крумплі`. No glosses |
| Review of E. Bárány, Hungaro-Ukrainica | https://real.mtak.hu/157685/1/article-p469.pdf | `облак` as a re-borrowing; `леґінь`, `ґазда` |

### Texts and studies of literary usage (for natural syntax)

| Source | URL | Contribution |
|---|---|---|
| D. Keshelia, «Родаки», published excerpt (Mukachevo area, central group) | https://tsn.ua/books/dmitro-keshelya-rodaki-790433.html | Running dialogue: `айбо, кедь, коби, лем, лиш, пак, туйки, типир, нараз, вшитко, нич, мож, сись/сесь, сесе, тото, ня, тя, му, го`, `сьме ся зобрали`, `-сьте`, `позерай`, `никай`, `видів / увиділи`, `уповіла`, `учинили`, `файно випозірує`, `красно дякуємо`, `вельми`, `наша файта`. Only 200 000 of about 221 000 characters were read |
| S. Nikolaev, M. Tolstaya, dialect texts from Ruska Mokra (2021) | https://inslav.ru/sites/default/files/isd23-nikolaev-tolstaya.pdf | Transcribed narrative, east Maramorosh: future `буду` + infinitive, past `писала-м`, `знали сьме`, conditional `бим`, free `ся`, `ми, ти, му, го`, `тот, тото, тоты, сесь`, `айбо, пак, лиш, туй, дуже`, `вун, кулько, пушла`, 1pl `идеме`, `дале`, `нич`, `кывати` (touch). First 100 000 of about 117 000 characters read |
| M. Tolstaya, on a dictionary of the Synevyr dialect | https://inslav.ru/images/stories/people/mtolstaya/MTolstaya_2002.pdf | Conditional `я бим казала`, `ты бись…`, `пак`; extraction was in a Latin-font encoding and is only partly legible |
| Article on dialect words in prose by Dochynets, Stanynets, Keshelia | https://real.mtak.hu/229218/1/9_Шилкіна_Барань.pdf | Glossed words: `чинити, видіти, гарувати, файно, хосен, челядник, крумплі, ґарадичі, пястук, копоня, цімбор, дітвак, вуйко`; `жеби`, `абись`, `най` in quotations |
| M. Yatskiv, phraseology in Keshelia's prose (2021) | https://visnyk-philology.uzhnu.edu.ua/article/download/257760/254594/593124 | `балта, цуравий, топанки, колодиця, красні`; quotations with `ня`, `ми`, `гі` |
| O. Kishko, N. Petii, on O. Lutsyshyna's «Іван і Феба» (2026) | https://mova.onu.edu.ua/article/download/357827/347369/841407 | `туй`, `авать` (or), `ушитко`, `біровати` («Не біровав-їсь?»), `неваловшний`, past `розвалив-їсь`, `ся` before the verb, `тя` |
| V. Greshchuk, dialect lexis in Petro Midianka's poetry (2021) | https://visnyk-philology.uzhnu.edu.ua/article/download/256757/253734/590787 | `бирувати` (be able), `рихтувати, ґаздувати, гарувати, банувати, хижа, тайстра, балта, топанки, калап, луфт, леґінь, варош, хосен`; much of the rest is mountain/Hutsul-area vocabulary and is not used |
| O. Kharkivska, dialect lexis in P. Skunts's poem (2022) | https://visnyk-philology.uzhnu.edu.ua/article/download/269040/264492/620492 | `позирати` (to look), `не годен`, `май файно`, `ня, ся, най`, `пропили-сьме`, `цімбор, дітвак, сарака, ґазда, ватра` |
| N. Bedzir, «Поетичний код Петра Мідянки» | https://www.ounb.uz.ua/content/files/7/1.pdf | `ся` used as "this" in Midianka; otherwise not used |
| V. Greshchuk, Hutsul lexis in Skliarenko's «Карпати» (2018) | https://iul-nasu.org.ua/pdf/ukrmova/4_18/11.pdf | `сокотити`, `айно`, `в'єдно`, `вантрувати` are attested here, but for the Hutsul part of Transcarpathia |

### Popular and press sources (context or second confirmation only)

| Source | URL | Contribution |
|---|---|---|
| UzhNU media centre, «Закарпатський діалект: що це таке…» (2019) | https://mediacenter.uzhnu.edu.ua/news/zakarpatskyj-dialekt-shho-tse-take-yak-vin-vynyk-ta-chomu-vazhlyvo-jogo-beregty/2019-11-13-37818 | Midianka and Chuchka on status; `фурт` (always), `варош`, `фірталь`; Russianisms named as foreign to the dialect |
| Radio Svoboda, O. Havrosh | https://www.radiosvoboda.org/a/25117918.html | Status debate; `тя, ня, му`; `цімбор, хижа` |
| «Голос Карпат», dialect word list | https://goloskarpat.info/culture/68b879b9781b9/ | No stated source. `дараб, бовт, варош, пак, нич, вшитко, вадь` agree with scholarly sources; `новинка` (newspaper) and `глядати` (search) occur only here |

### Opened for boundary-drawing

- O. Tymko-Ditko, adverbs of the Bačka Rusnaks (2021),
  https://visnyk-philology.uzhnu.edu.ua/article/download/257746/254581/593095 — `барз`, `вельо`, `гет`,
  `шицко` belong to Lemko/Bačka speech («барз вельо води» is quoted for Transcarpathian Lemkos).
- L. Koliesnik, Bukovyna dialect of Yuzhynets (2022),
  https://library.udpu.edu.ua/library_files/filologichniy-chacopys/2022/1/7.pdf — reflexive `си` and
  `май` comparatives in Bukovyna.
- L. Koliesnik, characterising names in Carpathian dialects (Gwary Dziś 2020),
  https://pressto.amu.edu.pl/index.php/gd/article/download/25877/23626/53699 — nothing used.
- Review of the second edition of Sabadosh's dictionary (Gwary Dziś 2023),
  https://pressto.amu.edu.pl/index.php/gd/article/download/40597/33995/91271 — the dictionary has over
  22 200 entries; no entries are reproduced.

### Could not be opened

- Sabadosh, «Словник закарпатської говірки села Сокирниця» itself; Hrytsak's dictionary materials;
  Dzendzelivskyi's atlas; Dobosh's «Синтаксис українських південнокарпатських говорів»; «Українські
  закарпатські говірки: Тексти» (2004); Kercha's dictionary; Chori. None were found as readable full text.
- UzhNU repository (dspace.uzhnu.edu.ua): after the first two successful reads almost every file link
  returned the repository home page instead of the document — among them «Закарпатський діалект»
  (lib/48769, most likely the 2009 bibliographic index), lib/22678, 24223, 22776, 36231, 42545, 42549,
  22153, 24070, 24116, 49380, 21987. Two more (lib/3687 on the Kholmovets dialect, lib/39965) were
  rejected for URL length. The item page https://dspace.uzhnu.edu.ua/jspui/handle/lib/48769 was blocked.
- https://en.wikipedia.org/wiki/Transcarpathian_dialect was blocked (a mirror was read instead).
- https://theses.cz/id/z06hyn/21233787 returned an anti-bot script, no content.
- ESU ids 14605 and 14611 are unrelated articles.

## 3. Base sub-dialect

Chosen: **central group (надборжавсько-латорицькі / березькі) with the adjacent west-Maramorosh speech
of the Khust area** — in short, a Borzhava–Maramorosh base.

Reasons:
1. Coverage. The opened descriptions cluster there: Dovhe and other Borzhava villages (Nimchuk's
   materials, Halas), Sokyrnytsia (Sabadosh), and Keshelia's prose from the Mukachevo area.
2. The two areas agree on everything the guide actually spells: `айбо`, `ги`, free `ся`, `ня/тя/го`,
   `-ме`, the past particles, `бим`, `май`, `туй`, `пак`, `вшитко`.
3. The main difference between them, the reflex of *o (`ÿ` in the centre, `у` in Maramorosh), cannot be
   shown with the standard alphabet anyway, and Keshelia (central) writes `у` (`хвуст`, `думів`).
4. The west (Uzh) group carries a Slovak layer (`облак`, `пец`) and the north (Verkhovyna) group shades
   into Boyko; both would pull the text toward other dialects.

Consequences and compromises:
- `кедь` was chosen for "if/when". ESU lists it among Slovak loans typical of the west, yet Keshelia uses
  it throughout; the Borzhava form is `кидь` (Dovhe) and Sokyrnytsia has `куй`. `кедь` is the most
  transparent of the three. This is the least clean choice in the guide.
- Hungarian loans from Simer (Uzh valley, Toder) were accepted only when a central or pan-regional
  source also has them or the word is on signs across the region (Shylov); `ґомбічка`, `лампаш`, `коцка`
  rest on Simer alone.
- German loans from Hvozdiak and Shetelia are given for "Transcarpathian dialects" as a whole, without
  village attribution; Hvozdiak says the older generation uses them most.

## 4. Decisions and rejected variants

| Topic | Decision | Rejected | Reason |
|---|---|---|---|
| Reflex of *o, *e | Standard `і` in content words; `у` in a closed list: `вун, тулько, кулько, пушов/пушла/пушли` | `ÿ/ӱ`; `у` everywhere (`кунь, нуч, стул`); `пуд` | No such letter; blanket `у` hurts readability and collides with technical words; `пуд` reads as the weight unit |
| `ы` | Not written (`хижа`, `був`) | `хыжа`, `быв` | Not in the Ukrainian alphabet; `и` after velars is real along the Latorytsia (ESU); the prose writers use `и`. Cost: the ы/и contrast, one of the dialect's best-known traits, is invisible |
| е → и | Only `типир` | `динь`, `вирьх`, `ни` for `не` | Would look like misspellings; `ни` collides with `ні` |
| 3rd person `-т` | Not used | `робит`, `кажут` | Real, but split inside the central area (ESU) and reads as a typo |
| 1sg `-ву`, contracted forms | Not used | `знаву`, `думаш`, `думат` | Confirmed (ESU) but opaque |
| 1pl | `-ме` | — | Confirmed in four sources, transparent |
| Past tense | `-им/-м`, `-ись/-сь`, `сьме`, `сьте`, used sparingly | `-єм`, `-єсь`, `-сьмо` | The requested `єм/єсь` spelling is the Galician/Boyko shape and is what the Galician guide uses; Transcarpathian sources give `-им`, `-м`, `сьме` |
| Conditional | `бим`, `бись` | `бых` | `бых` is the central form but needs `ы` |
| Future | `буду` + infinitive | `буду робив`; `му робити` | The first is attested in the opened sources only for Lemko; the second not at all for this base. See open questions |
| Pronouns | `ся` free, `ня, тя, го, ї, ми, ти, му`; `сись/сесе`, `тот/тото/тоти` | `тко/ко`, `што`; a feminine `сеся`, `тота` | `тко` is opaque, `што` reads as Russian; feminine forms were not attested on any opened page |
| "Very" | `дуже`, `вельми` | `барз`, `фест` | `барз` is Lemko; `фест` means "firm" here |
| "Only" | `лем`, `лиш` | — | Both in Keshelia; `лиш` also in Ruska Mokra |
| "Or" | `вадь`, `авадь` | `вать`, `авать` | Same word; the dictionary spelling was preferred |
| "Today" | `днесь` | `ниська` | `ниська` (Keshelia) is opaque |
| "That" (conjunction) | standard `що` | `ож` | Not confirmed (section 6) |
| Technical loans | `друт, мутерка, рула, луфт, вінкель, васерваґа` allowed only as household words in examples | Using them for course terms | Terms stay as in `i18n/uk/terms.md` |
| Field markers | Unchanged, including `У лозі:` / `У логу:` | Dialect forms of the markers | `FIELD_KEYS` in `scripts/build_site.py` matches them literally |

## 5. Confidence by feature group

| Group | Confidence | Basis |
|---|---|---|
| Sub-dialect division, phonetic reflexes | High | ESU, Wikipedia, Halas, Yusyp-Yakymovych agree |
| Enclitic pronouns, free `ся` | High | ESU plus four text sources |
| 1pl `-ме`, past particles, conditional `бим` | High | ESU, Dovhe, Ruska Mokra, Keshelia |
| Exact written shape of past particles (`-им` vs `-ем`, hyphen or not) | Medium | Sources transcribe differently; Keshelia writes `сьме` as a separate word, others attach with a hyphen or apostrophe |
| Conjunctions `айбо, ай, вадь, ци, ги, гиби, най, лем, лиш, пак` | High | Dictionary quotations plus texts |
| `кедь` for the chosen base | Medium | See section 3 |
| Parentheticals `никай, ачей, видав, чуй` | Medium | `видав` is glossed (Dovhe); the others are listed without glosses and their meaning is taken from Keshelia's contexts. One pass of the extraction read `никай` as "don't" |
| Word order with enclitics (second position, not clause-initial) | Medium | Consistent in all examples; no opened source states the rule |
| Hungarian loans | Medium–high | Several independent lists; `дараб` and `бовт` lean on weak or unglossed sources |
| German loans | Medium | Two papers agree, but without localisation and with a note on generational decline |
| Everyday verbs (`чинити, видіти, позирати, уповісти, біровати, байловати`) | High | Dictionary quotations plus texts |
| Demonstrative paradigm beyond masculine and neuter | Low | Not attested; guide keeps standard forms |
| Samples in section 9 of the guide | Medium | Composed by rule from confirmed pieces, not checked by a speaker |

## 6. Not confirmed (kept out of the guide)

- **`ож`** ("that") and **`оби`** ("in order to"): no opened page attests them. Keshelia's excerpt has
  `коби` and, in quotations elsewhere, `жеби` / `абись`. They are widely cited as Transcarpathian, so
  this is a gap in what could be opened, not evidence against them.
- **`сокотити`**, **`айно`**, **`в'єдно`**: attested only in a study of Hutsul-area lexis.
- **`новинка`** (newspaper), **`глядати`** (to search): only in the unsourced popular list.
- **`дараб`**: only the Wikipedia table and the popular list; kept in the guide with both tags because
  they are independent, but it is the weakest lexicon entry. Note `дараба` "raft" (Midianka, Hutsul area).
- **Future tense with `буду` + past participle** in Transcarpathian: the brief asked to consider it. The
  only description that mentions it for this dialect is a student summary on studfile.net (not used as
  a source), which says the infinitive type holds "except in Maramorosh speech"; ESU's Lemko article
  attests `буду робив` for Lemko. Ruska Mokra (east Maramorosh) and Dovhe both show `буду` + infinitive.
- **`му`-future** (`робити му`): nothing for this dialect.
- **`барз`**, **`фест` = "very"**: not Transcarpathian in the opened sources (Lemko; "firm").
- **`никати` vs `позирати`** distribution by area, and whether `позерати` or `позирати` is the base form.
- Background not taken from an opened page: the existence of a codified Rusyn standard in Slovakia and
  of Rusyn-language publishing in Transcarpathia; mentioned in section 1 only in general terms.

## 7. Open questions before any module is rewritten

1. Have one native speaker from the Irshava–Khust–Mukachevo area read the ten samples and the lexicon;
   the guide was built from descriptions, not from a speaker.
2. Check `ож`, `оби`, `сокотити`, `новинка`, `глядати`, `дараб` and the feminine demonstratives in the
   Sokyrnytsia dictionary (2021 edition) or Dobosh's syntax; add them to the guide only with a page reference.
3. Decide whether invisible `ы` is acceptable. If the site may use `ы` in this one language, `хыжа`,
   `быв`, `бых` become available and the text gets noticeably closer to how the dialect is written by
   its own speakers; the price is a non-Ukrainian letter in a version labelled Ukrainian dialect.
4. Decide `кедь` vs `кидь`.
5. Fix one spelling for the past particles (`налаштували сьме` / `сьме налаштували` / `-сьме`) and add
   it to a checker if the rewrite is automated.
6. The checker `scripts/check_i18n.py` should treat `uk-zakarpat` like `uk-galych`; `languages.json`
   needs an entry (`code: uk-zakarpat`, `fallback: uk`, name «Закарпатська говірка (експеримент)»). Not done here.
7. Density: the guide suggests one to three dialect features per sentence and none or one in sentences
   with numbers and parameters; this should be tested on one module before the whole tree is rewritten.
