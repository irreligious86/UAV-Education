---
id: tx-lua-widgets
title: "EdgeTX Lua widgets: your own telemetry screen"
level: L2
readingTime: 45 min
firmware: EdgeTX 2.12 (checked against 2.12.5) · ExpressLRS 4.1 · Lua 5.3.6
status: published
added: 2026-11-25
tags:
  - EdgeTX
  - Lua
  - telemetry
  - CRSF
  - radio
related:
  - link-edgetx
  - link-elrs
  - link-protocols
  - link-telemetry-radios
next:
  - ops-field
source: content/link/tx-lua-widgets.md
source_hash: 7fd626782f06
---

## summary
The stock widgets of a color radio show one number each. Your own Lua widget puts on one screen exactly what you need at the field: link quality with color, the battery converted to per-cell voltage, the flight controller mode, and the last values after a link loss. Going through the EdgeTX 2.12.5 source, this module covers the five types of Lua scripts and where each lives on the SD card, how a widget is built (`create`, `update`, `refresh`, `background`, `useLvgl`), when the radio calls each function, options, drawing on a color screen, reading CRSF/ELRS sensors, performance and debugging. The lab is the complete LinkBox widget: the code, a `luac` syntax check, and a test harness on desktop Lua 5.3 that replaces `lcd` and telemetry with stubs and runs a flight with a link loss. No hardware needed; installing it on a TX16S or TX15 comes at the end, if you want.

## theory
### Five script types and where they live
In EdgeTX, Lua is an extension language: the firmware gives the script functions (`getValue`, `lcd.drawText`, `playFile`…) and calls it in its own loop. A script's type is set by its folder on the SD card and by who runs it (paths in `radio/src/sdcard.h`, loading in `radio/src/lua/interface.cpp` and `widgets.cpp`):

| Type | Folder | Who runs it | Radios | Limits (2.12.5) |
|---|---|---|---|---|
| Widget | `/WIDGETS/<name>/main.lua` | the screen: the widget is placed in a zone | color only | folder name up to 13 characters; up to 50 options; ~20 000 instructions per call |
| Telemetry | `/SCRIPTS/TELEMETRY/<name>.lua` | the model's telemetry screen (Display) | monochrome only | file name up to 6 characters, up to 4 screens |
| Function | `/SCRIPTS/FUNCTIONS/<name>.lua` | the `Lua Script` special function, by a switch | all | name up to 8 characters |
| Mix | `/SCRIPTS/MIXES/<name>.lua` | Model → Mixer Scripts; outputs become mix sources | all built with `LUA_MIXER` | name up to 6 characters; up to 6 inputs and 6 outputs |
| Tool | `/SCRIPTS/TOOLS/` (a file, or a folder with `main.lua`) | by hand from the Tools / Apps menu | all | one at a time, full screen |

Notes on the table. Telemetry scripts are loaded only in `PCBTARANIS` builds, that is, on monochrome radios (`interface.cpp:706–729`); a TX16S has no such screens at all, and widgets do the same job. The name lengths come from `dataconstants.h`: `LEN_SCRIPT_FILENAME 6` for mix and telemetry, `LEN_FUNCTION_NAME 8` for function (the name is stored in the model without `.lua`). The `LUA_MIXER` build option is on by default in 2.12.5 (`radio/src/CMakeLists.txt:56`) and left `ON` in every target; without it only mix scripts disappear. There is also a sixth, rare type, `/SCRIPTS/RGBLED`, for radios with RGB lighting; the `RGB LED` special function runs it. At most nine persistent scripts can run at once on a color radio (mix + function + RGB LED) and seven on a monochrome one (mix + function + telemetry), `MAX_SCRIPTS`; the next one gives "Too many Lua scripts". Widgets do not count toward this: they have their own Lua environment. A widget folder name is no longer than 13 characters: the path buffer is `LEN_FILE_PATH_MAX + 6 + 5 + 1` (`widgets.cpp:46–48, 187, 203`), and the radio silently skips a longer folder.

{{diagram:edgetx-lua-script-types|The job decides the type: a screen on a color radio is only a widget, on a monochrome one a telemetry script; an action on a switch is a function script, a channel calculation a mix script.}}

The main selection rule: **a mix script is not for the primary channels.** If it crashes with an error, every mix line with its outputs is disabled (`mixer.cpp:899–906`), and the channel loses that source right in flight. Screens, voice and alarm logic belong in a widget or a function script; control belongs in ordinary mixes.

### Anatomy of a widget
A widget is a `main.lua` file that **returns a table** when executed. At startup the radio goes through the folders in `/WIDGETS`, executes each `main.lua` and reads the table's keys (`widgets.cpp:101–153`):

| Key | Required | When it is called | Arguments → what to return |
|---|---|---|---|
| `name` | yes | — | the string in the widget list |
| `options` | yes (`{}` is enough) | read at startup | the options table, see below |
| `create` | yes | the widget is placed in a zone or a model is loaded | `(zone, options, path)` → the widget object (usually a table) |
| `update` | no | the options or the zone size changed | `(widget, options)` |
| `refresh` | no (without it the widget is empty) | the zone is visible: every menu cycle | `(widget, event, touchState)` |
| `background` | no | the zone is **not** visible: every menu cycle | `(widget)` |
| `translate` | no | at startup | `(name, lang)` → the option label in the radio's language |
| `useLvgl` | no | at startup | `true` to draw through `lvgl.*`, see below |

A registration trap: the widget factory is created only if there are `name` and `create` (`widgets.cpp:146–148`) **and** an `options` table; without it `parseOptionDefinitions` returns `NULL` (`lua_widget_factory.cpp:276–280`), and the widget is simply missing from the list. There is no error message.

In 2.12 the `zone` table is relative: `x = 0`, `y = 0`, `w`, `h` are the zone size, and `xabs`, `yabs` its position on the screen (`lua_widget_factory.cpp:81–86`). Draw relative to `zone.x, zone.y` and do not hard-code the size: the same widget goes into a full-screen zone and into a narrow top-bar cell. The third argument of `create` is the path to the widget folder (`/WIDGETS/LinkBox/`), handy for images next to the code.

### Options
Each option is a table `{ name, type, default, min, max }`; for some types the fourth and fifth fields mean something else: for `CHOICE` the fourth is a list of strings, for `FILE` a folder. Option values are stored in the model **by index**, not by name, so inserting a new option in the middle of the list shifts the saved values for everyone who has already placed the widget. Add new options at the end.

| Constant | What the user chooses | Fields 3–5 | Defaults if not set |
|---|---|---|---|
| `VALUE` | an integer | default, min, max | min −100, max 100 |
| `SOURCE` | a source (stick, sensor, channel) | default (name or number) | — |
| `BOOL` | on/off | default 0/1 | 0 |
| `STRING` | a string | default | up to 255 characters (`textedit.h:61`) |
| `COLOR` | a color | default (`WHITE`, `lcd.RGB(…)`) | — |
| `TIMER` | timer 1–3 | default 0–2 | 0…`MAX_TIMERS−1` |
| `SWITCH` | a switch or LS | default, min, max | the whole range |
| `TEXT_SIZE`, `ALIGNMENT` | font size, alignment | default | — |
| `SLIDER` | a slider | default, min, max | 0…9 |
| `CHOICE` | one item from a list | default, list of strings | — |
| `FILE` | a file | default, folder to choose from | — |

There are at most 50 options (`MAX_WIDGET_OPTIONS`; extra ones are dropped). In OpenTX and early EdgeTX string options were limited to 8 characters, in 2.12 to 255; if you write a widget for older radios, keep strings short.

### When refresh and background are called
The EdgeTX menu cycle repeats every 50 ms (`tasks.cpp:51`, `MENU_TASK_PERIOD`), about 20 times a second. At every step `WidgetsContainer::refreshWidgets` decides for each zone: visible, redraw it (the redraw calls `refresh`); not visible, call `background` (`widgets_container.cpp:86–98`). Three consequences follow.

- **`background` is not called while the widget is on screen.** If an alarm or a minimum tracker lives only in `background`, it stays silent on a visible screen. Shared work (polling the sensors) goes into a function called from both.
- **You can draw only in `refresh`.** The screen buffer is handed to Lua only for the duration of `refresh` (`lua_widget.cpp:525–536`); `lcd.*` in `background` or `create` does nothing.
- **`event` is a number only in full-screen mode (0 if there is no event); `touchState` only on a touch in full-screen mode and only on touchscreen radios** (`lua_widget.cpp:512–522`). In an ordinary zone both are `nil`, and the radio's interface takes the presses. The touch constants (`EVT_TOUCH_*`) are defined only on touchscreen radios (`api_general.cpp:3387–3392`); elsewhere they are `nil`, so comparing `event == EVT_TOUCH_TAP` in an ordinary zone gives `nil == nil`, that is, true; that is why you check `event` first. In full-screen mode you get `EVT_VIRTUAL_ENTER`, `EVT_VIRTUAL_EXIT`, and the touches `EVT_TOUCH_FIRST`, `EVT_TOUCH_BREAK`, `EVT_TOUCH_TAP`, `EVT_TOUCH_SLIDE`; `touchState` is a table with `x`, `y`, `tapCount`, and while sliding also `slideX`, `slideY`, `swipeLeft`…

**The time budget.** Before every widget call a counter is set: the hook fires every 200 Lua virtual machine instructions, and on the 101st firing (about 20 000 instructions) `luaL_error("CPU limit")` is called (`widgets.cpp:37, 51–71`). In debug (DEBUG) builds, including some simulators, the limit is only printed to the debug output and does not stop the widget (`widgets.cpp:54–65`), so do not take the absence of an error there as proof. Any error in `create`, `update`, `refresh` or `background` disables that widget instance: the zone shows `ERROR in refresh(): …` in a small font in the warning color (`lua_widget.cpp:455–501`), and it is not called again until the widget is created anew (a model change, a screen edit, a reboot).

{{diagram:edgetx-widget-lifecycle|Only refresh draws, and only while the zone is visible; background runs in its place, update comes when the options or the zone change, and an error in any function or the instruction limit disables the widget instance until it is created again.}}

### useLvgl: another way to draw
The color radios' interface is built on the LVGL graphics library. Since EdgeTX 2.11.0 a widget can declare `useLvgl = true` and, instead of drawing pixels every frame, create objects once: `lvgl.label`, `lvgl.rectangle`, `lvgl.arc`, `lvgl.image`, buttons and input fields, or everything at once through `lvgl.build{…}`. What changes in the code (`lua_widget.cpp:259–264, 294–323`):

- `update` is called right after `create`, and that is where the interface is built;
- `refresh` is called with an empty buffer: `lcd.*` in it silently draws nothing, and only the logic remains;
- object properties can be given as functions (`text = function() return … end`), and the radio re-evaluates them after every `refresh`;
- in full-screen mode real buttons and input fields with focus and scrolling are available.

For an instrument panel of numbers like LinkBox, `lcd.*` is enough: it is easier to debug and to port to older versions. LVGL is for an interactive full-screen application with buttons.

### Drawing on a color screen
| Function | Arguments | Notes |
|---|---|---|
| `lcd.drawText` | `x, y, text [, flags [, inversColor]]` | `RIGHT`, `CENTER`, `VCENTER`, `INVERS`, `BLINK`, `SHADOWED` |
| `lcd.drawNumber` | `x, y, value [, flags]` | `value` must be an **integer**; fractions through `PREC1` / `PREC2` |
| `lcd.sizeText` | `text [, flags]` → `w, h` | for doing alignment yourself |
| `lcd.drawFilledRectangle` | `x, y, w, h [, flags [, opacity]]` | opacity: 0 is opaque, 15 fully transparent |
| `lcd.drawRectangle`, `lcd.drawLine`, `lcd.drawGauge` | — | frames, lines, gauges |
| `Bitmap.open` + `lcd.drawBitmap` | `bmp, x, y [, scale %]` | open the image once in `create`, not in `refresh` |
| `lcd.RGB` | `r, g, b` or `0xRRGGBB` | returns a color flag |

Flags are combined bitwise (`DBLSIZE | RED`; Lua 5.3 has the `|` operator, older examples use `+`). Font sizes: `TINSIZE`, `SMLSIZE`, `STDSIZE` (the default), `MIDSIZE`, `DBLSIZE`, `XLSIZE`, `XXLSIZE`; `BOLD`. Colors: the constants `WHITE`, `BLACK`, `RED`, `GREEN`, `YELLOW`, `ORANGE`, `GREY`… and the theme colors `COLOR_THEME_PRIMARY1`, `COLOR_THEME_WARNING`, with which the widget stays readable on a light theme (`api_colorlcd.cpp:1422–1455`).

Two number traps. EdgeTX is built with `LUA_32BITS` (`luaconf.h:64`): integers are 32-bit and fractions single precision. `lcd.drawNumber(x, y, 16.4)` and `string.format("%d", 16.4)` fail with "number has no integer representation", so print a voltage with `string.format("%.1f", v)` or as an integer in tenths with `PREC1`. The color radio's font is chosen at build time by the interface language (`gui/colorlcd/lv_conf.h:452–454`). The English font `lv_font_en_STD` has no Cyrillic (only Latin and a few symbols), and the Companion simulator always uses it (`lv_conf.h:472–475`); the Russian build gets only the letters that occur in the translation, and `XLSIZE` and `XXLSIZE` have no Cyrillic even there (`fonts/lvgl/make_fonts.sh:67–68, 323–335`). Write on-screen text in Latin characters.

### Reading telemetry
| Function | Returns | Without telemetry |
|---|---|---|
| `getValue(name or id)` | a number, a string (`FM`), a table (`GPS`) | **0** for all sensors (`api_general.cpp:345`) |
| `getSourceValue(name or id)` | `value, isCurrent, isFresh` | the last value and `isCurrent = false`; `nil` if the sensor never arrived |
| `getFieldInfo(name)` | `{ id, name, desc, unit }` | `nil` until the sensor is discovered |
| `getRSSI()` | for CRSF, the smoothed `RQly` (at most 99), alarm thresholds | 0 |
| `model.getInfo()` | `{ name, filename, labels, … }` | — |

How EdgeTX decides there is no link. For CRSF the stream counts as alive while `RQly` is above zero, and for 1 s after the last packet (`TELEMETRY_TIMEOUT10ms = 100`, `telemetry.h:46`; `crossfire.cpp:302–313`). As soon as the stream is gone, all sensors are marked stale (`telemetry.cpp:405–413`): `getValue` starts returning 0, and `getSourceValue` returns the last value with `isCurrent = false`. "Last known" is built on this: the voltage and mode at the moment of the loss are a hint about where and why the aircraft went down.

A sensor name is up to 4 characters (`TELEM_LABEL_LEN 4`), and it is the name from the model's telemetry list: if the user renamed `RxBt` to `Batt`, `getValue("RxBt")` returns 0. The CRSF/ELRS sensors that appear after `Discover new` (`telemetry/crossfire.cpp:44–80`, names in `translations/untranslated.h:116–227`):

| Sensor | Unit, precision | What Lua returns | Where from |
|---|---|---|---|
| `1RSS`, `2RSS` | dBm, integer | −63 | receiver |
| `RQly` | %, integer | 0–100 | receiver |
| `RSNR` | dB, integer | 9 | receiver |
| `ANT` | — | ELRS: 1 or 2 (1 is added to the number); TBS Crossfire: 0 or 1 | receiver |
| `RFMD` | — | the mode number | receiver |
| `TPWR` | mW | 0, 10, 25, 50, 100, 250, 500, 1000, 2000 (Crossfire can also have a second `TPWR` in dBm from LINK_TX frames) | radio module |
| `TRSS`, `TQly`, `TSNR` | dBm, %, dB | the return link | radio module |
| `RxBt` | V, 0.1 | 16.4 (a fraction); Betaflight sends it in 0.1 V steps | flight controller |
| `Curr` | A, 0.1 | 12.3 | flight controller |
| `Capa`, `Bat%` | mAh, % | integers | flight controller |
| `FM` | text | Betaflight: `"ACRO"`, `"ANGL"`, `"!FS!"`; before arming with the suffix `*` (ready), `!` (arming blocked), `?`, for example `"ANGL*"` | flight controller |
| `GPS` | coordinates | a table `{lat, lon}` | flight controller |
| `GSpd`, `Hdg`, `GAlt`, `Sats`, `Alt`, `VSpd` | km/h, °, m, count, m, m/s | numbers | flight controller |

What each sensor means and which thresholds people set is in the CRSF telemetry section of the `link-edgetx` module; how often packets arrive is in `link-elrs`.

{{lesson:link-edgetx|The table of CRSF sensors with thresholds, logical switches and voice alarms: what the widget only shows, the radio announces.}}

{{lesson:link-elrs|Packet rate and telemetry ratio set how often telemetry slots arrive: at 250 Hz and 1:64, once every 256 ms; no single sensor updates more often than that.}}

### Performance
- **Look a sensor up by name once.** `getValue("RQly")` scans the sensor list by string every time; `getFieldInfo` gives a numeric `id`, and reading by it is faster (the API description says so too). But `getFieldInfo` returns `nil` until the sensors are discovered, so the lookup is repeated once a second until they are found.
- **Do not create tables in `refresh`.** Every `{}` is work for the garbage collector on a radio with a few hundred kilobytes of memory. The widget object, lists and images are created in `create`.
- **The numbers change less often than the frames.** At 250 Hz and 1:64 a telemetry slot comes once every 256 ms, `refresh` once every 50 ms: four out of five frames draw the same numbers, and `RQly` and the flight controller sensors update even less often, since the link statistics (LINK) and data (DATA) packets share the same slots (`link-elrs`).
- **Measure, do not guess.** On the test harness the LinkBox code spends up to 393 instructions per `refresh` call, 2 % of the limit. The harness counts only the instructions of `main.lua`: `lcd.*` and `getSourceValue` on the radio are C functions, and the hook does not count them. You need the headroom: on the radio the same code shares the CPU with the mixer and the interface.

### Debugging
- **The EdgeTX Companion simulator.** The simulator window has a `Telemetry Simulator` (F4): in the `Internal Module` list choose `CRSF / ELRS`, and the fields `RQly`, `1RSS`, `RSNR`, `TPWR`, `RxBt`, `Curr`, `Capa`, `Bat%`, `FM`, `GPS` appear; the `Simulate` checkbox turns the telemetry stream on (the `Run` button there starts a GPS track). `Debug Output` (F6) shows the output of `print()`. `Reload Lua Scripts` (F7) rereads only mix, function and telemetry scripts; widget code is read at startup, so after editing a widget you close and reopen the simulator (`simulatormainwindow.cpp:149, 306–331`, `widgets.cpp:223–257`, `telemetrysimu.ui`). The simulator's SD card is set in the Companion settings; copy `/WIDGETS` there.
- **On the radio** the error is visible right in the zone: `ERROR in refresh(): /WIDGETS/LinkBox/main.lua:57: attempt to compare nil with number`, with the file, line and reason. The line number is there on the first run after an edit and in the simulator; when the radio loads the compiled `.luac`, the debug information has been stripped from it and the line disappears (`interface.cpp:567`), so for debugging delete the `.luac` and reboot. `print()` goes to the debug output (`TRACE`), which is not visible in a normal build; on the radio, debug with text on the screen.
- **On the computer**: `luac5.3 -p main.lua` (a syntax check) and a test harness with stubs, as in the practice. EdgeTX 2.12 uses Lua 5.3.6 (`thirdparty/Lua/src/lua.h:19–22`), the same version found in any Linux distribution, but in the firmware numbers are 32-bit (int32 integers, float fractions, `luaconf.h:64, 76–85`), while on the computer they are 64-bit; check rounding edge cases with margin.
- The radio compiles `.lua` into `.luac` next to the source by itself (mode `bt`, whichever is newer, `lua_api.h:36–42`; the simulator uses mode `T` and prefers `.lua`). If you fixed the script on the computer but the radio behaves the old way, check the file times or delete the `.luac`, and remember that widgets are reread only when the radio starts (or after leaving USB Storage mode).

### Where it fits in the system
- **Takes in:** CRSF telemetry sensors from the receiver and the flight controller through the radio module (`link-elrs`, `link-protocols`), sensor names and discovery and the radio's alarm logic (`link-edgetx`), the update rate from the ELRS packet rate and telemetry ratio.
- **Puts out:** to the pilot, LQ with color, per-cell voltage, the flight controller mode and the time since the link loss; to the procedure for finding a crashed aircraft (`ops-field`), the last values on the screen.
- **If you get this wrong:** a wrong cell count shows 4.2 V/cell on a pack that is really at 3.5 V/cell, and the pilot drains the battery to zero (`f-power`); a blank screen from `ERROR in refresh()` is something the pilot notices only at the field; a mix script instead of a widget disables a control channel when it crashes (`link-edgetx`, Mixer Scripts).

## practice
A lab without hardware: build the LinkBox widget, check its syntax and run it on the test harness. You need a computer with Lua 5.3 (`apt install lua5.3` on Debian/Ubuntu; WSL on Windows). Widget requirements: LQ in large digits colored by thresholds (a course guideline: 80 and up green, 50–79 yellow, below 50 red; the thresholds are options), `RxBt` with per-cell voltage, `FM`, a `1RSS` / `RSNR` / `TPWR` line, after a link loss the last values in gray and a seconds counter, and a compact view for a small zone (the large layout from 180 × 100 pixels, a course guideline).

### Step 1. Sensors and options
The sensor list is a constant; there are four options: the cell count (0 = auto), two LQ thresholds and the text color. The option order is fixed from the start: values are stored by index.

The auto estimate takes ⌈V / 4.40⌉: 4.40 V is slightly above a full LiHV cell (4.35 V), a margin for measurement error. With a divisor of exactly 4.35, a full 6S LiHV pack (26.1 V) would give 26.1 / 4.35 = 6.0000…01, and after rounding up, 7S. The estimate is right as long as the per-cell voltage is above 4.40·(n−1)/n: 3.30 V for 4S, 3.67 V for 6S, 3.85 V for 8S. So the auto estimate can get a discharged pack wrong (and for 8S and up, even a storage-charged one): 21.0 V is both a full 5S and an empty 6S. The estimate is latched in `sample` on the first value after each connection, even if the widget is not on screen at that moment, and it is not reset in `update`, which the radio calls on every change of options and zone size; only a new connection (a new battery) or a change of the `Cells` option resets it. For flying, set the cell count with the option.

An `RxBt` value ≤ 4.5 V (the threshold is a course guideline) is taken by the widget as already per cell: that is how Betaflight sends it with `report_cell_voltage = ON` (in 0.1 V steps), or it is a 1S pack.

### Step 2. The full code
The file `tools/lua/LinkBox/main.lua` in the course repository; on the radio, `/WIDGETS/LinkBox/main.lua`.

```lua
-- LinkBox: ELRS/CRSF link and battery widget for EdgeTX colour radios.
-- Checked against the EdgeTX 2.12.5 Lua API (widgets.cpp, lua_widget.cpp, api_general.cpp).
-- Install: /WIDGETS/LinkBox/main.lua on the SD card, then add the widget to a screen zone.
-- Screen strings are ASCII on purpose: the English-build font has no Cyrillic glyphs.

local SENSORS = { "RQly", "RxBt", "FM", "1RSS", "RSNR", "TPWR" }
local LOOKUP_PERIOD = 100   -- 10 ms ticks: retry sensor lookup once per second
local CELL_MAX_V = 4.40     -- just above LiHV full charge (4.35 V): auto cell count only
local PER_CELL_MAX = 4.5    -- RxBt at or below this is already per cell (course choice)

local options = {
  { "Cells",  VALUE, 0, 0, 14 },    -- 0 = auto (latched at the first reading after each connect)
  { "LQwarn", VALUE, 80, 1, 100 },  -- course reference thresholds, not a standard
  { "LQcrit", VALUE, 50, 1, 100 },
  { "Text",   COLOR, WHITE },
}

-- getSourceValue (EdgeTX 2.12) returns value, isCurrent, isFresh and keeps
-- the last value after the link is lost. Fallback for radios without it:
-- getValue returns 0 when telemetry is not streaming.
local function readSource(id)
  if getSourceValue then
    return getSourceValue(id)
  end
  local v = getValue(id)
  if v == 0 then return nil, false end
  return v, true
end

local function resolveIds(w)
  local now = getTime()
  if now - w.lastLookup < LOOKUP_PERIOD then return end
  w.lastLookup = now
  for i = 1, #SENSORS do
    local name = SENSORS[i]
    if not w.ids[name] then
      local info = getFieldInfo(name)   -- nil until the sensor is discovered
      if info then w.ids[name] = info.id end
    end
  end
end

local function sample(w)
  resolveIds(w)
  local up = false
  for i = 1, #SENSORS do
    local name = SENSORS[i]
    local id = w.ids[name]
    if id then
      local v, current = readSource(id)
      if v ~= nil and current then
        if name ~= "RQly" then
          w.last[name] = v
        elseif v > 0 then                 -- RQly 0 = link just dropped: keep last good
          w.last[name] = v
          up = true
        end
      end
    end
  end
  if up then
    if not w.up then w.cells = nil end   -- new connection: maybe a new pack
    local v = w.last.RxBt
    if w.cells == nil and v and v > PER_CELL_MAX then
      w.cells = math.ceil(v / CELL_MAX_V) -- latched here, visible or not
    end
    w.lastGood = getTime()
    local lq = w.last.RQly
    if w.lqMin == nil or lq < w.lqMin then w.lqMin = lq end
  end
  w.up = up
end

local function cellCount(w, v)
  if v <= PER_CELL_MAX then return 1 end -- 1S, or FC already sends the average per cell
  if w.options.Cells > 0 then return w.options.Cells end
  return w.cells or math.ceil(v / CELL_MAX_V)
end

local function lqColor(w, lq)
  if lq >= w.options.LQwarn then return GREEN end
  if lq >= w.options.LQcrit then return YELLOW end
  return RED
end

local function create(zone, opts)
  local w = { zone = zone, options = opts, ids = {}, last = {},
              lastLookup = -LOOKUP_PERIOD, lastGood = nil, up = false,
              cells = nil, lqMin = nil }
  return w
end

local function update(w, opts)
  -- called on every option change and zone resize: keep the latched count
  if opts.Cells ~= w.options.Cells then w.cells = nil end
  w.options = opts
end

local function background(w)
  sample(w)          -- called only while the widget is not on screen
end

local function drawBig(w, x, y, txt)
  local L = w.last
  if not L.RQly and not L.RxBt then
    lcd.drawText(x + 4, y + 2, "NO TLM", SMLSIZE | RED | BLINK)
    return
  end
  local dim = w.up and txt or GREY
  local lq = L.RQly
  if lq then
    lcd.drawText(x + 4, y + 2, "LQ", SMLSIZE | dim)
    lcd.drawNumber(x + 4, y + 14, lq, DBLSIZE | (w.up and lqColor(w, lq) or GREY))
    if w.lqMin then
      lcd.drawText(x + 4, y + 52, string.format("min %d", w.lqMin), SMLSIZE | dim)
    end
  end
  local v = L.RxBt
  if v then
    local n = cellCount(w, v)
    if n == 1 then
      lcd.drawText(x + 90, y + 2, string.format("%.2fV", v), MIDSIZE | dim)
      lcd.drawText(x + 90, y + 30, "per cell", SMLSIZE | dim)
    else
      lcd.drawText(x + 90, y + 2, string.format("%.1fV", v), MIDSIZE | dim)
      lcd.drawText(x + 90, y + 30, string.format("%.2fV/c %dS", v / n, n), SMLSIZE | dim)
    end
  end
  if L.FM then
    lcd.drawText(x + 90, y + 52, tostring(L.FM), SMLSIZE | BOLD | dim)
  end
  local row = y + 74
  lcd.drawText(x + 4, row, string.format("1RSS %s", L["1RSS"] or "--"), SMLSIZE | dim)
  lcd.drawText(x + 4, row + 16, string.format("RSNR %s  TPWR %s", L.RSNR or "--", L.TPWR or "--"), SMLSIZE | dim)
  if not w.up then
    local msg = "NO TLM"
    if w.lastGood then
      msg = string.format("NO LINK %ds", (getTime() - w.lastGood) // 100)
    end
    lcd.drawText(x + w.zone.w - 4, y + 2, msg, SMLSIZE | RIGHT | RED | BLINK)
  end
end

local function drawSmall(w, x, y, txt)
  local L = w.last
  if not L.RQly then
    lcd.drawText(x + 2, y + 2, "NO TLM", SMLSIZE | RED)
    return
  end
  local col = w.up and lqColor(w, L.RQly) or GREY
  lcd.drawText(x + 2, y + 2, string.format("LQ %d", L.RQly), SMLSIZE | col)
  if L.RxBt then
    lcd.drawText(x + 2, y + 18, string.format("%.1fV", L.RxBt), SMLSIZE | (w.up and txt or GREY))
  end
end

local function refresh(w, event, touchState)
  sample(w)
  -- event is nil unless the widget is in full-screen mode;
  -- EVT_TOUCH_TAP is nil on radios without a touch screen
  if event and (event == EVT_VIRTUAL_ENTER or event == EVT_TOUCH_TAP) then
    w.lqMin = nil                         -- reset the flight minimum
  end
  local z = w.zone
  local txt = w.options.Text
  if z.w >= 180 and z.h >= 100 then    -- big layout size: course choice
    drawBig(w, z.x, z.y, txt)
  else
    drawSmall(w, z.x, z.y, txt)
  end
end

return { name = "LinkBox", options = options, create = create,
         update = update, refresh = refresh, background = background }
```

What in the code comes from the theory. Sensor polling (`sample`) is called from both `refresh` and `background`, so the LQ minimum, the cell count and the loss time are tracked even while another screen is open. The IDs are looked up once a second until they are found. `RQly = 0` is not stored as "last good": at the moment of the loss the module manages to send a zero. LQ is printed with `drawNumber` (an integer), the voltage with `string.format("%.1f")` (a fraction). The LQ minimum is tracked from the moment the widget is created; in full-screen mode pressing Enter or a touch resets it. Before comparing with `EVT_TOUCH_TAP` the code checks that `event` is not `nil`: on a radio without a touchscreen that constant is `nil`, and without the check the minimum would be reset every frame.

### Step 3. Syntax check
```
$ luac5.3 -p tools/lua/LinkBox/main.lua && echo "luac5.3 -p: OK"
luac5.3 -p: OK
```
`luac -p` catches only syntax: an unclosed `end`, a stray comma. Errors such as comparing `nil` with a number show up only at run time, and that is what the next step is for.

### Step 4. The test harness
The file `tools/lua/harness.lua` in the course repository replaces the EdgeTX globals with stubs: `lcd.drawText` and `lcd.drawNumber` print the coordinates, flags and text, and `drawNumber`, like the real `luaL_checkinteger`, checks that the value has no fractional part; `getFieldInfo` returns `nil` until a sensor is "discovered"; `getSourceValue` returns the value and the `isCurrent` flag; `getTime` is a controllable clock in 10 ms ticks. The harness loads `main.lua` with `loadfile`, checks the widget table, calls `create` with a 225 × 122 zone and runs 14 frames: no sensors → a link with 6S → LQ 62 → LQ 38 → the widget hidden, only `background` running → link loss → a new 4S battery → Enter in full-screen mode → `update` under load → a battery swap → the auto-estimate trap → the `Cells = 6` option → per-cell voltage from the flight controller → a 70 × 36 top-bar zone. Instructions are counted by `debug.sethook` with a count of 1, the same mechanism EdgeTX uses to limit widgets; the harness counts only instructions from `main.lua`, because its stubs are written in Lua, while on the radio these are C functions the hook does not count.

```
$ lua5.3 tools/lua/harness.lua tools/lua/LinkBox/main.lua
widget 'LinkBox': 4 options, keys create/update/refresh/background = true/true/true/true
t=  0.0 s  1. sensors not discovered yet  [147 VM instructions]
  text   (  4,  2) SML|BLINK|RED NO TLM
t=  1.5 s  2. link up, 6S pack at 24.6 V  [393 VM instructions]
  text   (  4,  2) SML|WHITE LQ
  number (  4, 14) DBL|GREEN 100
  text   (  4, 52) SML|WHITE min 100
  text   ( 90,  2) MID|WHITE 24.6V
  text   ( 90, 30) SML|WHITE 4.10V/c 6S
  text   ( 90, 52) SML|BOLD|WHITE ACRO
  text   (  4, 74) SML|WHITE 1RSS -63
  text   (  4, 90) SML|WHITE RSNR 9  TPWR 250
t=  4.0 s  3. LQ 62 (between LQcrit 50 and LQwarn 80)  [346 VM instructions]
  …
  number (  4, 14) DBL|YELLOW 62
  …
t=  4.5 s  4. LQ 38 (below LQcrit)  [309 VM instructions]
  …
  number (  4, 14) DBL|RED 38
  …
t=  4.6 s  5. widget hidden: background() samples, 0 draw calls  [154 VM instructions]
t=  9.7 s  6. link lost 5 s ago: last good values (from background), grey  [322 VM instructions]
  text   (  4,  2) SML|GREY LQ
  number (  4, 14) DBL|GREY 41
  text   (  4, 52) SML|GREY min 38
  text   ( 90,  2) MID|GREY 21.9V
  text   ( 90, 30) SML|GREY 3.65V/c 6S
  text   ( 90, 52) SML|BOLD|GREY ANGL
  text   (  4, 74) SML|GREY 1RSS -104
  text   (  4, 90) SML|GREY RSNR -4  TPWR 1000
  text   (221,  2) SML|RIGHT|BLINK|RED NO LINK 5s
t= 15.0 s  7. reconnect with a fresh 4S pack (cell count re-detected)  [352 VM instructions]
  …
  text   (  4, 52) SML|WHITE min 38
  text   ( 90,  2) MID|WHITE 16.4V
  text   ( 90, 30) SML|WHITE 4.10V/c 4S
  text   ( 90, 52) SML|BOLD|WHITE ACRO*
  …
t= 15.1 s  8. full screen, ENTER pressed: LQ minimum reset  [296 VM instructions]
  …
  number (  4, 14) DBL|GREEN 100
  text   ( 90,  2) MID|WHITE 16.4V
  …
t= 15.2 s  9. update() (zone or option change) under load keeps the latched 4S  [304 VM instructions]
  …
  text   ( 90,  2) MID|WHITE 12.9V
  text   ( 90, 30) SML|WHITE 3.23V/c 4S
  …
t= 15.3 s  10. pack swapped: link lost  [285 VM instructions]
  …
  text   (221,  2) SML|RIGHT|BLINK|RED NO LINK 0s
t= 16.0 s  11. auto count trap: 6S at 3.50 V/cell reads as 5S  [336 VM instructions]
  …
  text   ( 90,  2) MID|WHITE 21.0V
  text   ( 90, 30) SML|WHITE 4.20V/c 5S
  …
t= 16.1 s  12. Cells option = 6: correct per-cell value  [298 VM instructions]
  …
  text   ( 90, 30) SML|WHITE 3.50V/c 6S
  …
t= 16.2 s  13. FC sends average per cell, 0.1 V steps (report_cell_voltage = ON)  [281 VM instructions]
  …
  text   ( 90,  2) MID|WHITE 3.90V
  text   ( 90, 30) SML|WHITE per cell
  …
t= 16.2 s  14. topbar-size zone 70x36
  text   (  2,  2) SML|GREEN LQ 100
  text   (  2, 18) SML|WHITE 3.9V
max main.lua VM instructions per refresh: 393 of the ~20000 widget budget (2.0 %)
```

The output is abridged: "…" marks skipped lines of the same frames; you get the full log by running the harness yourself. The harness paid for itself twice. In the first version the "≤ 4.5 V means it is already per cell" check came after the `Cells` option, and in frame 13 the widget divided 3.9 V by 6 and showed `0.65V/c 6S`. And the cell count was reset in `update`: in frame 9, after the zone change, it would have been recomputed from the sagging 12.9 V as ⌈12.9 / 4.40⌉ = 3, that is, `4.30V/c 3S` on a pack that is really at 3.23 V/cell. On the radio this would have looked like "the battery is full" at the end of a flight; here it was one line of log and a fix to two functions.

### Step 5. The Companion simulator (optional)
Copy the `LinkBox` folder into `/WIDGETS` on the simulator's SD card and open the simulator for a color radio (TX16S). In `Telemetry Simulator` (F4) choose `Internal Module` = `CRSF / ELRS`, set `RQly = 100`, `RxBt = 24.6`, `FM = ACRO`, tick the `Simulate` checkbox, run `Discover new` and place LinkBox in a zone. Untick `Simulate`: after a second the digits turn gray and the `NO LINK` counter starts. After editing the code, close and reopen the simulator: F7 (`Reload Lua Scripts`) does not reread widgets.

### Moving to real hardware
The radio: a color EdgeTX 2.11 or newer (TX16S, TX16S MK3, TX15, Jumper T15/T16/T18 and the like); an aircraft with ELRS and telemetry enabled in the flight controller (`link-protocols`). Props off: the check is done on the bench.

1. **Backup.** The radio in `USB Storage (SD)` mode; copy the whole SD card to the computer. Abort criterion: if the copy did not read completely, do not go further.
2. Copy `LinkBox` into `/WIDGETS/` and reboot the radio (or leave USB Storage mode; widgets are reread then). On the main screen, open the screen setup, choose a zone of at least 180 × 100 pixels (for example, a layout with one large zone) and the `LinkBox` widget. In the options set `Cells` to your battery's cell count.
3. Power the aircraft, `Telemetry → Discover new`. No later than a second after the sensors appear, the widget shows LQ, voltage and mode.
4. Compare with the telemetry screen: `RQly`, `RxBt`, `FM`, `1RSS`, `RSNR`, `TPWR` match the widget's numbers; per-cell voltage = `RxBt` / `Cells` to within 0.01 V.
5. Walk away with the aircraft or cover the receiver antenna with your hand: the LQ color changes to yellow below 80 and red below 50. Unplug the aircraft battery: after 1 s the digits are gray and `NO LINK` counts seconds. Plug it back in: the digits get their color back, and `min` shows the worst LQ.
6. Abort criteria: the screen shows `ERROR in …` or the radio has become slow to respond to buttons; delete the `LinkBox` folder from the SD card and restore the backup; the widget does not affect the channels, but the check is repeated on the computer.

Acceptance criteria on hardware: the six values match the telemetry screen; the transition "link up → down → up" behaves as in frames 2, 6 and 7 of the harness; in a top-bar zone, the compact two-line view.

Self-check: the lab is done when:
- (1) `luac5.3 -p` on your `main.lua` prints `OK`;
- (2) the test harness passes all 14 frames without a Lua error, and the numbers match the reference: frame 2 `100`, green, `24.6V`, `4.10V/c 6S`; frame 3 `62` yellow; frame 4 `38` red; frame 6 all values gray, `41` and `21.9V` from `background`, `NO LINK 5s`; frame 7 `4.10V/c 4S`, `min 38`, `ACRO*`; frame 9 `3.23V/c 4S`; frame 11 `5S`; frame 12 `3.50V/c 6S`; frame 13 `3.90V`, `per cell`;
- (3) the maximum number of `main.lua` instructions per call is no more than 2000 (10 % of the limit, a course guideline); the reference has 393;
- (4) for the hardware path, the acceptance criteria from the "Moving to real hardware" section are met.

Items 1–3 are the computer path, item 4 only if you have a radio and an aircraft.

**Reference answer for self-check.** A correct widget gives the output from step 4 (in full when you run the harness); the coordinates may differ if you changed the layout, but the colors, texts and frame order may not. Four typical mistakes. Frame 6 shows `0` instead of `41` and `21.9V`: reading through `getValue` without checking `isCurrent`, which returns zero after the loss; if it shows `38` and `22.1V`, polling is not called from `background`. Frame 9 shows `3S`: the cell count is reset in `update`. Frame 13 shows `0.65V/c 6S`: the "≤ 4.5 V" check comes after the `Cells` option. The harness fails with "number has no integer representation": a fractional voltage got into `drawNumber` or `%d`.

## diagnostics
- **Symptom:** the widget is not in the list, and there is no error either.
  Possible cause: the file is not at `/WIDGETS/<name>/main.lua`; the folder name is longer than 13 characters; the table has no `name`, `create` or `options`; the file does not return the table (the `return` at the end is missing).
  What to do: check the path and the last line of the file; add `options = {}`; reboot the radio, since the widget list is read at startup.
- **Symptom:** the zone shows `ERROR in refresh(): …: attempt to compare nil with number`.
  Possible cause: the sensor is not discovered yet or was renamed, `getValue` / `getSourceValue` returned `nil` or 0, and the code compares without checking.
  What to do: check the value for `nil` before comparing; take the sensor name from the model's telemetry list; after the fix, restart the simulator or the radio (on the radio, leaving USB Storage mode is enough); F7 in the simulator does not reread widgets.
- **Symptom:** `ERROR in refresh(): … number has no integer representation`.
  Possible cause: `lcd.drawNumber` or `string.format("%d")` got a fraction (`RxBt`, `Curr`, `VSpd`, with a precision of 0.1–0.01).
  What to do: `string.format("%.1f", v)` or `lcd.drawNumber(x, y, math.floor(v * 10 + 0.5), PREC1)`.
- **Symptom:** `ERROR in refresh(): CPU limit`.
  Possible cause: more than ~20 000 instructions per call: a loop over all sensors with a lookup by name every frame, building strings in a loop, large tables.
  What to do: cache the `id`, move preparation into `create` and `update`, measure the instructions on the harness with `debug.sethook`. In a DEBUG build of the simulator the limit does not trigger; check on the harness or on the radio.
- **Symptom:** after a link loss the widget shows zeros instead of the last values.
  Possible cause: reading through `getValue`, which returns 0 without a telemetry stream.
  What to do: `getSourceValue` and the `isCurrent` flag; for older firmware, do not overwrite the saved value with zero.
- **Symptom:** the per-cell voltage is 0.7–0.8 V too high (for example `4.20V/c 5S` on a 6S) or too low (`7S` on a full 6S LiHV with a 4.35 divisor).
  Possible cause: the auto estimate of the cell count from a discharged pack (below 4.40·(n−1)/n V per cell), or a divisor right at the full-charge boundary; or the estimate is recomputed in `update` from the sagging voltage.
  What to do: set `Cells` explicitly; a divisor of 4.40; latch the estimate on connection, not in `update`.
- **Symptom:** the per-cell voltage is about 0.6–0.7 V (for example 3.9 / 6 = `0.65V/c`).
  Possible cause: `report_cell_voltage` is on in Betaflight, `RxBt` is already per cell, and the widget divides it again.
  What to do: the "≤ 4.5 V means it is already per cell" check before the division, as in LinkBox, or turn off `report_cell_voltage`.
- **Symptom:** an alarm or the LQ minimum is tracked only while the screen with the widget is open (or the other way round).
  Possible cause: the logic is only in `refresh` or only in `background`; they are never called at the same time.
  What to do: a shared polling function called from both.
- **Symptom:** after setting the options in a new widget version, the thresholds have "moved" into other fields.
  Possible cause: a new option was inserted in the middle of the list; values are stored by index.
  What to do: add new options only at the end; after changing the order, set the options again in every model.
- **Symptom:** you fixed the script on the computer, but the radio or the simulator behaves the old way.
  Possible cause: on the radio, a newer `main.luac` sits next to it and the radio loaded that; in the simulator (mode `T`, `.lua` preferred), the widget simply was not restarted.
  What to do: on the radio, delete the `.luac` or copy the `.lua` with the current time and reboot; close and reopen the simulator (F7 does not reread widgets).

## checklist
- Before any change on the radio, a copy of the whole SD card.
- The widget is at `/WIDGETS/<name>/main.lua` (folder name up to 13 characters), and the table has `name`, `options`, `create`.
- After editing the widget, restart the radio or the simulator.
- Drawing only in `refresh`; polling and logic in a shared function called from `refresh` and `background`.
- Sensors are looked up with `getFieldInfo` and cached by `id`; the lookup repeats until they are discovered.
- Last values through `getSourceValue` and `isCurrent`, not through `getValue`.
- Fractions through `string.format("%.1f")` or `PREC1`, not straight into `drawNumber`.
- The cell count is set with the option; the auto estimate (⌈V / 4.40⌉) is latched on connection and is right only for a charged pack.
- New options are added at the end of the list.
- On-screen text in Latin characters.
- `luac5.3 -p` and the test harness pass; `main.lua` uses less than 10 % of the limit per call (a course guideline).
- On the radio the widget's values match the telemetry screen, and a link loss is handled.

## references
- EdgeTX, source code, tag v2.12.5: radio/src/lua (widgets.cpp, lua_widget.cpp, lua_widget_factory.cpp, interface.cpp, api_general.cpp, api_colorlcd.cpp, api_colorlcd_lvgl.cpp) | https://github.com/EdgeTX/edgetx/tree/v2.12.5/radio/src/lua | primary | A
- EdgeTX v2.12.5: telemetry/crossfire.cpp and translations/untranslated.h, the CRSF sensors | https://github.com/EdgeTX/edgetx/blob/v2.12.5/radio/src/telemetry/crossfire.cpp | primary | A
- EdgeTX v2.12.5: dataconstants.h and sdcard.h, name lengths and SD card folders | https://github.com/EdgeTX/edgetx/blob/v2.12.5/radio/src/dataconstants.h | primary | A
- EdgeTX Lua Reference Guide (the Lua API documentation repository) | https://github.com/EdgeTX/lua-reference-guide | primary | A
- Lua 5.3 Reference Manual | https://www.lua.org/manual/5.3/ | primary | A
- EdgeTX Companion: the simulator, Telemetry Simulator and Debug Output (companion/src/simulation) | https://github.com/EdgeTX/edgetx/tree/v2.12.5/companion/src/simulation | primary | A

## notes
Checked against the EdgeTX v2.12.5 source (commit 0ebe2e9): the script types, the widget table keys, the arguments of `create` and `refresh`, the condition for calling `background`, the instruction limit, the option types and count, the `lcd.*` functions and constants, the behavior of `getValue` / `getSourceValue` / `getRSSI` on telemetry loss, the names and units of the CRSF sensors, the Companion simulator windows. The LinkBox code was checked with `luac5.3 -p` and the test harness on Lua 5.3.6 (the same version as in the firmware, but with 64-bit numbers instead of 32-bit); the author has not run it on a radio: the pixel layout is fitted to a 225 × 122 zone and may need font adjustments. Not checked: which EdgeTX version first had `getSourceValue` (2.12.5 has it; the code keeps a fallback through `getValue` for older firmware). The `lv_font_en_STD` font has no Cyrillic: checked against the character ranges in the font file itself.
