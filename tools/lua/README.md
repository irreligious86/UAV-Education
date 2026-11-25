# EdgeTX Lua examples

Code from the course module `tx-lua-widgets` («Lua-виджеты EdgeTX: свой экран телеметрии»).

## LinkBox

`LinkBox/main.lua` is a telemetry widget for EdgeTX colour radios (TX16S, TX15, T15, T16 and similar),
written against the EdgeTX 2.12.5 Lua API. It shows:

- link quality `RQly` with colour thresholds (green ≥ 80, yellow ≥ 50, red below; both are widget options
  and course reference values, not a standard) and the lowest LQ since the widget was created
  (reset with Enter or a tap in full-screen mode);
- receiver battery `RxBt` with a per-cell estimate (`Cells` option; 0 = auto: ⌈V / 4.40⌉, latched at the
  first reading after each connect, even while the widget is hidden). The estimate is right only above
  4.40·(n−1)/n V per cell — 3.30 V for 4S, 3.67 V for 6S, 3.85 V for 8S — so a discharged pack (and an
  8S+ pack even at storage voltage) can be miscounted: set the cell count explicitly;
- values ≤ 4.5 V are treated as already per cell (Betaflight `report_cell_voltage`, 0.1 V steps) or 1S;
- flight mode `FM`, `1RSS`, `RSNR`, `TPWR`;
- the last good values in grey and a `NO LINK <s>` counter after telemetry is lost.

### Install

1. Back up the whole SD card.
2. Copy the `LinkBox` folder to `/WIDGETS/` on the SD card (result: `/WIDGETS/LinkBox/main.lua`).
   Widget folder names longer than 13 characters are skipped silently.
3. Restart the radio, open the screen setup, pick a zone at least 180 × 100 px and select `LinkBox`.
   Smaller zones (e.g. the top bar) get a two-line compact view.
4. Run `Telemetry → Discover new` with the aircraft powered; the widget finds the sensors by name
   within one second of discovery.

### Test on a computer

```
luac5.3 -p LinkBox/main.lua
lua5.3 harness.lua LinkBox/main.lua
```

`harness.lua` stubs `lcd`, `getFieldInfo`, `getSourceValue` and `getTime` and replays a short flight
(link up, LQ drop, hidden widget, link loss, reconnect, pack swap). It counts only instructions of
`main.lua`. EdgeTX 2.12 uses Lua 5.3.6, so desktop `lua5.3` runs the same language version, but the
firmware is built with `LUA_32BITS` (int32 integers, float32 numbers) while desktop Lua uses 64-bit
numbers: leave margin around rounding boundaries.

After editing a widget, restart the radio or the Companion simulator: widgets are read only at start
(the simulator's F7 "Reload Lua Scripts" reloads mix/function/telemetry scripts, not widgets).

License: same as the course content.
