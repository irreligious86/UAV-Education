# Terminology: Russian → Czech

Binding for every Czech translation of the course (interface, modules, quizzes, tasks, glossary). Plain
technical Czech as Czech FPV shops, flight-controller manuals and university theses write it. Parameter
names, commands, MAVLink messages, flight-mode names, code and unit symbols are never translated
(`ATC_RAT_RLL_P`, `ARMING_CHECK`, `Loiter`, `AltHold`, `ROS 2`, `MAVLink`). How each decision was reached,
and the sources behind the tags in the note column, are in `docs/reviews/i18n-research-cs.md`.

None of Betaflight Configurator, INAV Configurator, QGroundControl or Mission Planner ships a Czech
locale, so Czech pilots work in the English UI. Every on-screen label (tab, button, mode, option) stays in
English exactly as the program shows it; the Czech word goes around it: „na záložce *Motors*“, „režim
`ANGLE`“.

## Style rules

- **Form of address: vykání.** The source's «ты» becomes lowercase „vy“ with plural imperatives
  („zkontrolujte“, „nastavte“, „nebojte se ptát“), „váš“, „vám“. Every Czech FPV tutorial and hardware
  manual opened addresses the reader this way; none uses „ty“. Walk-throughs may use the inclusive first
  person plural („v této kapitole si projdeme“, „ladíme konstantu“), which the same sources mix in. Never
  capitalise „Vy/Váš“ (that is letter style). Avoid past-tense sentences addressed to the reader
  („udělal jste“): they force a gender; rephrase („po dokončení“, „pokud je hotovo“).
- **Tone:** direct and slightly informal, as in the source. Short sentences, imperatives, no officialese.
  Slang seen in the community („lipolka“, „baterka“, „vrtulky“, „mód“) is not used.
- **Numbers: exactly as in the source.** The course writes decimal points because the same numbers are
  code, parameters and task answers; do not convert to the Czech decimal comma (`4.2 V`, not `4,2 V`), and
  do not regroup thousands. Answers and tolerances in quiz and task banks stay byte-identical.
- **Units:** SI symbols in Latin script with a space after the number: h, min, s, ms, Hz, kHz, V, mV, A,
  mA, mAh, Wh, W, Ω, dB, dBm, g, kg, m, cm, mm, km/h, m/s, °C, ° (no space before °). Russian В, А, мАч,
  Гц, мс, Вт, дБ, г, кг, м, ч, мин, с map one to one. `C` (discharge rate), `S`/`P` (cells), `KV`, `eRPM`,
  `RPM` stay as written. Percent takes a space in prose (`60 %`), never inside code or parameters.
- **Quotes:** „…“ (inner ‚…‘) for the source's «…». Dash: en dash with spaces ( – ) for the source's em dash.
- **Spelling:** *řídicí* (short i, "serving to control") in *řídicí jednotka, řídicí systém, pozemní řídicí
  stanice*. The one exception is the legal term *dálkově řídící pilot* (long í, "the pilot who is
  controlling"), spelled as in Regulation (EU) 2019/947. Many sources misspell the first as *řídící*; do not copy.
- **English terms kept as they are** (lowercase, declined only where it reads naturally): failsafe, firmware
  (*firmwaru, firmwarem*), ESC, FC, VTX, OSD, GPS/GNSS, IMU, EKF, PID, blackbox, bind, stack, BEC, UART, RSSI,
  setpoint (alongside *žádaná hodnota*), wind-up, bias, drift, waypoint, geofence, RTL/RTH, smoke stopper.
  Czechised and declined normally: *armování / armovat*, *kalibrace*, *telemetrie*, *logování*, *trim*, *mixer*.
- **roll / pitch / yaw vs klonění / klopení / zatáčení.** English lowercase *roll, pitch, yaw* for anything
  the reader meets on screen or on the sticks: stick channels, PID axes, rates, log traces, mixer
  („P na ose roll“, „plyn a yaw na levé páce“). Czech *klonění, klopení, zatáčení* for the physical motion in
  aerodynamics, flight mechanics and control theory („moment klopení“, „stabilita v klonění“), with the
  English word in brackets at first mention in a module: „klopení (pitch)“. Do not use *bočení*, *náklon/sklon*
  as axis names, or *rotace kolem osy Z* as a substitute.
- **throttle → plyn** always („přidejte plyn“, „páka plynu“, „50 % plynu“); *throttle* only as an on-screen label.
- **ESC vs regulátor.** The hardware is *regulátor otáček (ESC)* at first mention, then *ESC* or
  *regulátor*. In any module that also discusses control loops, call the hardware *ESC* only: *regulátor*
  there means the PID controller.

## Diagnostics field markers

Use exactly these strings in `## diagnostics`; the build parser matches them (the item line as written,
detail lines case-insensitively by their beginning).

| field | marker in the translation | accepted variants | source |
|---|---|---|---|
| symptom | `- **Příznak:**` | `- Příznak:` | Симптом |
| cause | `Možná příčina:` | | Возможная причина |
| evidence | `V logu:` | `V logu/na přístroji:`, `Co je vidět v logu:`, `Co je vidět:` | В логе / Что видно |
| consequence | `Důsledky:` | | Последствия |
| fix | `Co udělat:` | `Co zkontrolovat:`, `Co zkontrolovat/udělat:`, `Co udělat (zkontrolovat/opravit):`, `Co udělat (zkontrolovat nejdřív):` | Что сделать / Что проверить |

Strings for `scripts/build_site.py`: `SYMPTOM_KEYS` += `"**Příznak:**"`, `"Příznak:"`; `FIELD_KEYS`:
cause += `"možná příčina"`; fix += `"co udělat"`, `"co zkontrolovat"`; evidence += `"v logu"`, `"co je vidět"`;
consequence += `"důsledky"`.

## Terms

Source tags in brackets are the Czech sources the term was read in (key in the research notes).
"unconfirmed" = not found in a Czech source that could be opened; a native reviewer should check it.

| ru | cs | note |
|---|---|---|
| БПЛА | bezpilotní letadlo (UAV) | legal and generic term [EU947, AMC, Hlinomaz]; theses also *bezpilotní letoun* [Červenka, Kovář, Kment], avoid it for copters (*letoun* = fixed wing). Abbreviation stays UAV |
| БАС | bezpilotní systém (UAS) | „bezpilotní letadlo a vybavení pro jeho řízení na dálku“ [EU947, epravo] |
| дрон, коптер, мультикоптер | dron, koptéra, multikoptéra | [Rot-1st, Červenka, Nejedlý, Hlinomaz]; *kvadrokoptéra* for a quad; not *multirotor* |
| летающее крыло, самолёт | samokřídlo, letoun | *samokřídlo* [Bukovský]; *letoun* [Bukovský, Kment, Denk]; *letadlo* is any aircraft. ArduPilot "Plane" keeps its name. *létající křídlo* unconfirmed, do not use |
| полётный контроллер | řídicí jednotka (FC) | [Rot-BF, Pilotix, Červenka, Bukovský]; first mention may be *letová řídicí jednotka* [Hlinomaz]. Not *letový kontrolér / řadič / ovladač* |
| прошивка | firmware | [Rot-BF, SPF3, Hlinomaz, Nejedlý]; verb: *nahrát firmware* |
| регулятор (ESC) | regulátor otáček (ESC) | [Bukovský, Hlinomaz, Nejedlý, Rot-BF]; then ESC / regulátor, see style rule |
| рама, луч | rám, rameno | [Červenka, Nejedlý, Hlinomaz] |
| пропеллер, винт | vrtule | [Rot-BF, Rot-1st, Wiki-Vrtule, AMC, all theses]; never *propeler*; *list vrtule* = blade, *stoupání* = pitch [Quiz] |
| аккумулятор, банка | baterie, článek | *baterie* in practitioner texts [EdgeTX, Rot-BF, Rot-1st, Pilotix, AMC]; *akumulátor* in theses [Červenka, Nejedlý, Bukovský] is allowed where chemistry or type is the topic (*Li-Ion akumulátor*). *článek* [Rot-1st, Červenka, Hlinomaz]; `4S` stays |
| пульт, аппаратура | vysílačka | [Rot-BF, Rot-1st, Rot-TX]; *RC vysílač* [Červenka, EdgeTX] is the formal synonym; not *rádio*, *ovladač* |
| приёмник / передатчик | přijímač / vysílač | [EdgeTX, Rot-BF, SPF3, Hlinomaz] |
| видеопередатчик | videovysílač (VTX) | [Pilotix]; then VTX [Rot-BF] |
| наземная станция | pozemní stanice (GCS) | [Hlinomaz, Kovář]; long form *pozemní řídicí stanice* (cf. *pozemní kontrolní stanice* [Červenka]) |
| бортовой компьютер | palubní počítač (companion) | [Červenka] |
| режим полёта | letový režim | [EdgeTX, Bukovský]; „v režimu ANGLE“ [Rot-1st]; not *mód* |
| висение | vis | „ve visu“ [Rot-1st, Hlinomaz, Nejedlý]; verb *viset*; „plyn ve visu“. Noun *visení* unconfirmed, do not use |
| газ | plyn | [EdgeTX, Rot-1st, Rot-TX, Červenka, Hlinomaz] |
| крен / тангаж / рыскание | klonění / klopení / zatáčení | [Kment; Denk, Wiki-Křid: klonění, zatáčení; Bukovský: klopení]; English roll / pitch / yaw on sticks, axes and logs [Rot-BF, Rot-TX], see style rule. Angle values: *úhel klonění*, *úhel klopení*, *kurz* [Červenka] |
| взлёт / посадка | vzlet / přistání | [Rot-1st, Bukovský, Denk, AMC]; not *start* |
| полёт, полётный | let, letový | [Quiz, EdgeTX]; *předletová kontrola* [Rot-1st] |
| датчик | senzor | [Červenka, Hlinomaz, Kovář, Kment]; not *čidlo*, *snímač* |
| дальномер | dálkoměr | „laserový dálkoměr“ [Hlinomaz, Kovář] |
| оценка состояния | odhad stavu | [Mráz, Kašpar] |
| помеха | rušení; šum | *rušení* = interference [Hlinomaz, Kovář, Quiz]; *šum* = noise in a signal [Nejedlý, Kovář, Mráz]; by context |
| напряжение / ток / сопротивление / мощность | napětí / proud / odpor / výkon | [EdgeTX, Fluke, SPF3, Rot-BF]; *výkon* [EdgeTX] |
| провод, разъём, пайка | vodič, konektor, pájení | [SPF3, Fluke, Pilotix, Rot-tools]; *kabel* for a multi-core cable or harness [Rot-tools]; verb *pájet / připájet* |
| отказ, отказоустойчивость | porucha, odolnost proti poruchám | [Pánek, AMC, Kovář]; *selhání* for a function that stops working, *výpadek* for loss of signal or power [Blum] |
| настройка (тюнинг) | nastavení; ladění | *nastavení* = setup [Rot-BF, EdgeTX]; *ladění* = tuning („naladění PID“ [Hlinomaz], „ladíme konstantu KP“ [ČVUT-reg]) |
| лог, журнал | log; záznam | *log, logování* [Rot-BF, EdgeTX, Denk]; „v logu“; *záznam* for a written record [AMC] |
| курс / трек / модуль / путь | kurz / okruh / modul / cesta | *kurz, modul* [Moodlista, CUNI-Moodle]; *okruh* (track) and *cesta* (path) unconfirmed; a Czech learning app says *trasa* for path [Mimo] |
| лабораторная | laboratorní úloha | unconfirmed; not *laboratoř* (that is the room) |
| квиз | kvíz | [Quiz]; Czech Moodle says *test* [Moodlista], kept for exams only |
| итоговый проект | závěrečný projekt | unconfirmed |
| проект | projekt | [Mimo] |
| освоен | zvládnuto | module status; unconfirmed |
| пройден | dokončeno | steps and paths; *absolvovat* for a whole course [Moodlista]; *dokončeno* itself unconfirmed |
| сдан / не сдан | splněno / nesplněno | quiz, tasks: *splnění* [CUNI-Moodle]; exam: *složeno / nesloženo* („složení zkoušky“ [AMC]); project: *odevzdáno* („odevzdání úkolu“ [CUNI-Moodle]) |
| экзамен | zkouška | [AMC] |
| балл | body | „dostat body“ [Moodlista]; score of a module: *počet bodů* |
| справочник | příručka | reference section; unconfirmed in this sense („uživatelská příručka“ [Quiz] is a user manual) |
| глоссарий | slovník pojmů | [Moodlista] |
| журнал фейлов | deník poruch a chyb | unconfirmed; *porucha* [AMC, Pánek], *chyba* [Pánek] |
| задача с числовым ответом | úloha s číselnou odpovědí | unconfirmed |
| чек-лист | kontrolní seznam | [AMC]; *předletová kontrola* for the pre-flight one [Rot-1st] |
| источники | zdroje | unconfirmed |
| диагностика | řešení problémů | section heading [Hyundai]; *diagnostika* for the activity (*diagnostické LED* [Pilotix]) |
| симптом / возможная причина / что сделать | příznak / možná příčina / co udělat | *Příznak, Možná příčina* [Hyundai, Blum]; *co udělat* replaces the manuals' *Řešení* to mirror the source; markers above |
| последствия | důsledky | diagnostics field; unconfirmed |
| аккаунт, вход, регистрация | účet, přihlášení, registrace | *účet* [Moodlista]; *registrace* [epravo, Moodlista]; *přihlášení* [Moodlista] (there in the sense of enrolment; as "sign in" unconfirmed) |
| администрация, админка | administrátoři, administrace | *administrátor* [Moodlista]; *administrace* (admin page) unconfirmed |
| группа (учебная) | skupina | [CUNI-Moodle, Moodlista] |
| арминг / дизарм | armování / disarm | *armovat, armování* [Rot-BF, Rot-1st]; „přepínač ARM v poloze disarm“ [Rot-1st]; a Czech verb for disarm is unconfirmed, write *vypnout armování* |
| failsafe | failsafe | [EdgeTX, Rot-BF, Rot-1st]; masculine, „nastavit failsafe“ |
| стики | kniply | [Rot-BF, Rot-1st]; *páka plynu* for the throttle stick [EdgeTX, Rot-TX] |
| тумблер, переключатель | přepínač | [Rot-1st, Rot-TX]; EdgeTX's own label is *spínač* [EdgeTX] |
| канал | kanál | [Rot-TX, EdgeTX] |
| телеметрия | telemetrie | [EdgeTX, Rot-TX, SPF3, Kovář] |
| калибровка | kalibrace | [EdgeTX, Rot-BF] |
| гироскоп / акселерометр / магнитометр | gyroskop / akcelerometr / magnetometr (kompas) | [Rot-BF, Hlinomaz, Nejedlý] |
| ИНС, IMU | inerciální měřicí jednotka (IMU) | [Kašpar] |
| мотор, бесколлекторный мотор | motor, bezkartáčový motor | [Hlinomaz]; *střídavý motor* [Červenka, Nejedlý] only when the electrical type matters |
| обороты | otáčky | [Wiki-Vrtule, Bukovský]; unit `RPM` as in the source |
| тяга | tah | [Wiki-Vrtule, Hlinomaz, Nejedlý, Kment, Denk]; *statický tah* [Hlinomaz] |
| подъёмная сила / сопротивление (аэро) | vztlak / odpor | [Kment, Denk, Hlinomaz, Wiki-Vrtule] |
| угол атаки | úhel náběhu | [Kment, Wiki-Vrtule] |
| центр тяжести | těžiště | [Kment, Bukovský, Hlinomaz, Nejedlý] |
| элероны, руль направления | křidélka, směrovka | [Wiki-Křid, Denk, Bukovský]; *výškovka* (elevator) and *elevony* unconfirmed |
| сервопривод | servo | [Bukovský, Denk] |
| крутящий момент | krouticí moment | [Wiki-Vrtule] (source spells *kroutící*) |
| ПИД-регулятор | PID regulátor | [Wiki-PID, ČVUT-reg]; *proporcionální / integrační / derivační složka* [Wiki-PID] |
| ошибка регулирования | regulační odchylka | [Wiki-PID, Wiki-Reg, ZČU-LS2, Nejedlý, Hlinomaz] |
| уставка | žádaná hodnota (setpoint) | [Wiki-PID, ČVUT-reg]; *požadovaná hodnota* [Nejedlý, Wiki-Reg] is the same thing, do not mix |
| управляющее воздействие | akční zásah | [Nejedlý]; as a variable: *akční veličina* [Wiki-PID] |
| коэффициент усиления | zesílení | [Wiki-PID, ZČU-LS2, Nejedlý] |
| перерегулирование | překmit | [Wiki-PID, ČVUT-reg, Nejedlý]; textbook synonym *přeregulování* [ZČU-LS2] not used |
| статическая ошибка | trvalá regulační odchylka | [Wiki-PID, ČVUT-reg] |
| обратная связь | zpětná vazba | [Wiki-Reg, ČVUT-reg] |
| передаточная функция | přenosová funkce | [ZČU-LS2, Kment]; short *přenos* [Wiki-PID] |
| контур, замкнутый / разомкнутый | regulační smyčka, uzavřená / otevřená | [ZČU-LS2, Wiki-Reg]; *regulační obvod* [Wiki-Reg] for the whole loop as a system |
| запас по фазе / по усилению | bezpečnost ve fázi / v zesílení | [ZČU-LS2]; the variant *fázová / amplitudová bezpečnost* is unconfirmed |
| устойчивость | stabilita | [Wiki-PID, ZČU-LS2, Kment] |
| возмущение | porucha (poruchová veličina) | [Wiki-PID, Wiki-Reg, ZČU-LS2]; same word as "fault": make the sense clear from context |
| полоса пропускания | šířka pásma | [ZČU-LS2] |
| частота дискретизации | vzorkovací frekvence | [Rot-BF]; *perioda vzorkování* [ZČU-LS2] |
| фильтр Калмана, EKF | Kalmanův filtr, rozšířený Kalmanův filtr (EKF) | [Mráz, Kašpar, Nejedlý] |
| шум измерений / шум процесса | šum měření / procesní šum | [Kašpar, Mráz]; *kovarianční matice* [Mráz, Kašpar] |
| комплементарный фильтр | komplementární filtr | [Nejedlý] |
| слияние данных датчиков | fúze senzorů | „multisenzorická fúze“, „fúze měření“ [Kašpar] |
| короткое замыкание | zkrat | [Rot-tools, SPF3] |
| цепь, нагрузка | obvod, zátěž | [Fluke] |
| просадка напряжения | úbytek napětí | [Fluke] |
| стабилизатор, BEC | stabilizátor napětí (BEC) | [SPF3, Pilotix] |
| мультиметр | multimetr | [Rot-tools, Fluke] |
| паяльник, припой, флюс | páječka, pájka (cín), tavidlo | [Rot-tools] |
| термоусадка | smršťovací bužírka | [Rot-tools] |
| контактная площадка | pájecí ploška | „plošky“ [SPF3, Pilotix] |
| пищалка | bzučák | [Pilotix] |
| очки (FPV) | brýle | [Rot-1st] |
| дальность | dosah | radio link [Rot-TX] |
| краш, падение | pád | [Rot-1st] |
| оператор / внешний пилот | provozovatel / dálkově řídící pilot | [EU947, AMC, epravo, Quiz]; in hobby context simply *pilot* |
| открытая / специальная / сертифицированная категория | otevřená / specifická / certifikovaná kategorie | [EU947, epravo] |
| прямая видимость (VLOS) / BVLOS | vizuální dohled (VLOS) / mimo vizuální dohled (BVLOS) | [EU947, Quiz] |
| максимальная взлётная масса | maximální vzletová hmotnost (MTOM) | [EU947] |
| полезная нагрузка | užitečné zatížení | [EU947, AMC, Quiz] |
| посторонние люди | nezúčastněné osoby | [EU947] |
| геозона | zeměpisná zóna | [EU947]; *geofence* of the firmware stays English |
| возврат домой | návrat domů (RTL/RTH) | [AMC] |
| потеря связи | ztráta spojení | [EU947, AMC]; *ztráta signálu* for GNSS [Quiz] |
| аварийные процедуры | nouzové postupy | [AMC] |
| миссия, точка маршрута | mise, waypoint | *mise* [Červenka, Kovář]; no settled Czech word for waypoint (*bod trasy* unconfirmed) |
| автопилот | autopilot | [Kovář, Kment, Bukovský, Denk] |
| симулятор | simulátor | [Rot-TX]; *simulace* [Kovář] |

## Additions from the pilot batch (2026-11-14)

Decisions taken while translating the first five modules; binding for later batches so the same thing
reads the same everywhere. All are unreviewed by a native speaker.

| ru | cs | note |
|---|---|---|
| об/мин, об/с | ot/min, ot/s | `RPM` stays where the source writes RPM |
| мкс, мОм, Н·м, рад/с, В/эл. | µs, mΩ, N·m, rad/s, V/článek | |
| 60% | 60 % | space before % in prose and table cells; never inside code or parameter values |
| заармился / не армится | dron se armoval / nejde armovat | |
| флаг запрета арма | příznak blokující armování | open: collides with the diagnostics marker „Příznak:“ — keep the marker, reviewer to pick a better noun |
| аппарат | stroj | „dron“ where the source means a multicopter specifically |
| сборка | stavba | |
| журнал аппарата | deník stroje | |
| крыло (fixed wing in general) | letoun | `Flying Wing` preset name unchanged; „samokřídlo“ only for a tailless wing |
| оценщик | estimátor | |
| слайдеры | posuvníky | |
| насыщение | saturace | |
| реактивный момент | reakční moment | |
| перелёт (overshoot) | překmit | |
| кейс | případová studie | |
| термический разгон | tepelný únik (thermal runaway) | |
| тяговооружённость, T/W | poměr tahu k tíze (T/W) | |
| вкладка | záložka | on-screen tab names themselves stay English |
| бэкап | záloha | |
| спутники | satelity | |
| дом (RTH) | domov | |
| начало работы (tag) | začínáme | |
| любая прошивка | libovolný firmware | |

Kept in English (tuning jargon): propwash, bounce-back, flip, freestyle, rates, notch, target, preset, fix,
step response, overshoot (as a metric name; „překmit“ in running prose).
Module titles in cross-references follow `i18n/cs/data.json` once it is filled; until then translate them
consistently with the module's own `title`.
Past-tense first-person checklist items are rephrased to avoid grammatical gender („mám spočítaný…“).

## Reviewer corrections (2026-11-14)

From the independent review of the pilot batch (`docs/reviews/i18n-review-cs-pilot.md`). Where a row
conflicts with a table above, this one wins.

| ru | cs | note |
|---|---|---|
| флаг запрета арма | flag blokující armování; first mention in a module „flagy blokující armování (Arming Disable Flags)“, then *flag* | replaces „příznak blokující armování“. *příznak* is reserved for «симптом» and the `Příznak:` marker. Declined *flag, flagu, flagy, flagů*; avoid the locative plural (write „mezi flagy“). The only Czech source found keeps the English label: „Arming Disable Flags – důvody, proč nejde armovat“ [Rot-BF]; a Czech noun for it was not found |
| арм-флаги, флаги арма (in `status`) | flagy blokující armování | not „příznaky armování“ |
| взлётный вес | vzletová hmotnost | a quantity given in g or kg is *hmotnost*; *tíha* only for the force (ratio name „poměr tahu k tíze“, „tah se rovná tíze“). „vzletová tíha“ is not used |
| разобранный пример | řešený příklad | not „rozebraný příklad“ (calque) |
| метрики по манёврам, медиана по манёврам | metriky pro jednotlivé manévry, medián přes manévry | „po manévrech“ reads as "after the manoeuvres" |
| лабораторная засчитывается | laboratorní úloha je splněna | per сдан → splněno; not „se uznává“ |
| один шаг за раз | vždy jen jeden krok | not „jeden krok najednou“ |
| фиксация (результата) | uložení | not „zafixování“ |
| логи (locative plural) | u logů, podle logů, v logu | rephrase instead of „v lozích / po lozích“ |
| стек (the software project) | projekt, firmware | *stack* stays reserved for the FC+ESC hardware stack |

## Translator rules from the pilot review (2026-11-14) — binding

1. **„příznak“ is reserved for «симптом / признак»** and the `**Příznak:**` marker. A software flag is
   *flag*: first mention in a module „flagy blokující armování (Arming Disable Flags)“, then *flag*.
   Before submitting, grep your files: every „příznak“ outside the marker must translate «симптом/признак».
2. **Disarm:** verb *disarmovat*, noun *disarm* (parallel to *armovat / armování*). Unverified with a
   native speaker; use it consistently so it can be changed in one pass.
3. **hmotnost vs tíha:** anything in g or kg is *hmotnost* („vzletová hmotnost“); *tíha* only for the force
   and in the fixed name „poměr tahu k tíze (T/W)“.
4. **Banned calques → Czech pattern**

   | Russian pattern | not | write |
   |---|---|---|
   | distributive «по X» (метрики по манёврам) | po X | pro jednotlivé X / přes X |
   | «рабочий» (рабочий метод) | pracovní | funkční / který funguje |
   | «на фоне» | na pozadí | při / uprostřed |
   | «за раз», «один шаг за раз» | najednou | vždy jen (jeden krok) |
   | «разобранный пример» | rozebraný příklad | řešený příklad |
   | «фиксация» (результата) | fixace | uložení / zaznamenání |
   | predicate instrumental («делает X бесполезным») | dělá X bezcenným | a verb: „znehodnotí X“ |
   | unit after a comma («тяга, г») | …, g | … v g |
   | «живёт» about data/settings | žije | je uložen / najdete v |
   | «в логах» | v lozích / v logech | v logu / u logů / podle logů |

5. **Telegraphic source lines** (mostly safety steps and checklists) get a full Czech verb or noun:
   «перед этим — мультиметром» → „předtím kontrola multimetrem“; «с готовностью перехватить» →
   „buďte připraveni převzít řízení“.
6. **Checklist items and quiz `explain` lines must be unambiguous when read alone**
   („Na stole je dron vždy bez vrtulí“, not „Na stole nejsou vrtule“).
7. **State vs ability:** «армится» → „se armuje“, «не армится» → „nejde armovat“.
8. **Quiz self-check:** for every question confirm the keyed option is still the only correct one in Czech.

## Additions from batch 0 (foundation, 2026-11-14) — binding, unreviewed by a native speaker

| ru | cs | note |
|---|---|---|
| панч | punch | gloss once: „prudké přidání plynu naplno“ |
| десинк | desync | |
| колокол мотора | zvon motoru (rotor) | |
| пакет, сборка (АКБ) | baterie / sada článků | |
| паспорт сборки / журнал сборки | pasport stavby / deník stavby | |
| втулки (демпферы FC) / стойки / демпфер | silentbloky / (distanční) sloupky / tlumič | |
| поролон / мачта GPS | molitan / stožárek | |
| пад / шина BEC | (pájecí) ploška / větev BEC | |
| таргет / бод | target / baudů | |
| диск-актуатор | aktuátorový disk | |
| относительная поступь J | rychlostní poměr J | |
| нагрузка на диск | plošné zatížení disku | |
| КПД | účinnost | |
| шаг (винта) | stoupání | |
| силовая установка | pohonná jednotka | |
| рабочая точка | pracovní bod | established term; the «рабочий → funkční» rule does not apply here |
| тяговый стенд | měřicí stolice | |
| клиппинг | clipping (saturace) | |
| консольная балка | vetknutý nosník | |
| ЭДС / ШИМ | elektromotorické napětí / PWM | |

Task `unit` values are localised (min, A, ot/min, m/s, N/m², g, W, Hz). Terse quiz `explain` lines may be
expanded just enough to read unambiguously alone; never change which option is correct.

## Additions from batch 1 (regulations, field ops, mechanics, electricity, components) — binding, unreviewed

| ru | cs | note |
|---|---|---|
| регулятор (authority) | letecký úřad / úřad pro civilní letectví | never „regulátor“ |
| площадка / зона полётов | letová plocha / letový prostor | |
| журнал оператора / полётов / вылета / площадки | deník provozovatele / letů / letu / letové plochy | |
| наблюдатель / старший | pozorovatel (spotter) / vedoucí | |
| борт | stroj; palubní elektronika | by context |
| вылет / прогон | výjezd, let / zkouška naostro | |
| почти-инцидент | skoroincident (near miss) | |
| привязной стенд | zkušební stav s upoutaným strojem | |
| гс | gf | |
| вес (сила) / плечо L | tíha / rameno síly | frame arm stays „rameno“ |
| предельная скорость / координированный вираж | mezní rychlost / koordinovaná zatáčka | |
| крен 30° / наклон | úhel klonění 30° / náklon | |
| А·ч, мА·ч, Вт·ч | Ah, mAh, Wh | |
| C-рейтинг | hodnocení C (C-rating) | |
| прозвонка | test spojitosti | |
| межвитковое замыкание | mezizávitový zkrat | |
| разбаланс | nevyvážené články | |
| LiPo-пакет (сумка) | LiPo vak | |
| чёрный ящик / даташит | blackbox / datasheet | |
| крепёж | spojovací materiál | |
| цифра (видео) | digitál | |

Subscripts with Russian labels are Czechised consistently: Rвн → R_i, U_хх → U_0, U_борта → U_paluby,
P_пот → P_ztr, R_сумм → R_celk, I_ср → I_stř, m_рамы → m_rámu. Voice phrases are Czech („Arm povolen“,
„Vzlétám“, „Rozumím“, „Volno“, „Přistaň“). Russian prose inside inline code examples (log lines) is translated.

## Additions from batch 2 (method, case studies, troubleshooting, ESC firmware, Remote ID) — binding, unreviewed

| ru | cs | note |
|---|---|---|
| журнал изменений | deník změn | |
| инженерная папка / трассируемость | inženýrská složka / trasovatelnost | |
| паспорт аппарата | karta stroje | «паспорт сборки» stays „pasport stavby“ |
| стендовые тесты | testy na měřicí stolici | «на стенде без пропов» (bench) → „na stole bez vrtulí“ |
| полевой тест | test v terénu | |
| авария / исправление / корневая причина | nehoda / náprava / kořenová příčina | |
| система прекращения полёта | systém ukončení letu (FTS) | |
| аварийный выключатель | nouzový vypínač | |
| неисправность | závada | |
| прозвонить | změřit průchodnost | noun: „test spojitosti“ |
| холодная пайка | studený spoj | |
| фен (паяльный) | horkovzdušná pistole | |
| тайминг / демагнитизация | časování (timing) / demagnetizace | |
| срыв синхронизации | ztráta synchronizace (desync) | |
| ключи (ESC) | spínací tranzistory | |
| загрузчик / кирпич | bootloader / cihla | |
| безопасность (security) | zabezpečení | safety stays „bezpečnost“ |
| поверхность атаки | plocha útoku (attack surface) | |
| широковещание / маячок / глушение | všesměrové vysílání / maják / rušení (jamming) | |
| полезная нагрузка (пакета) | datová část | payload of the aircraft: „užitečné zatížení“ |
| метка времени / сборка прошивки | časová značka / sestavení firmwaru | |
| одиночная точка отказа | jednotlivé místo poruchy (single point of failure) | |

Feet stay `ft`, `ft/min` in accident reports. A quiz stem may be turned from a sentence completion into a
question if Czech grammar needs it; options keep their order and the keyed answer.
