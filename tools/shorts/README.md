# Shorts renderer

Scripts that render the silent vertical short videos of the «Betaflight изнутри» series
(tuning, chip-tuning, personalization). The videos themselves are published elsewhere and are
**not** stored in this repository; only the sources are kept so a video can be re-rendered after a fix.

## Requirements

- Python 3 with Pillow
- ffmpeg on `PATH`
- Fonts: Inter (`/usr/share/fonts/opentype/inter`) and DejaVu Sans Mono — paths are set at the top of `render.py`

## Usage

```bash
cd tools/shorts
python3 v_rates_ff.py preview   # one still per scene -> out/<name>_prev/
python3 v_rates_ff.py render    # full MP4 -> out/<file>.mp4
```

`out/` is ignored by git.

## Layout

| File | Video | Block |
|---|---|---|
| `render.py` | shared framework: palette, fonts, cards, code blocks, hook/end cards, parallel render | — |
| `v_rates_ff.py` | T1 Rates and feedforward | tuning |
| `v_throttle.py` | T2 Throttle: dynamic idle, TPA, thrust linear | tuning |
| `v_mechanics.py` | T3 Mechanics before PID (motor balance) | tuning |
| `v_esc_inside.py` | C1 ESC firmware inside (Bluejay / AM32) | chip-tuning |
| `v_cloud_build.py` | C2 Betaflight Cloud Build | chip-tuning |
| `v_elrs_inside.py` | C3 ExpressLRS inside | chip-tuning |
| `v_boot_logo.py` | P1 OSD boot logo (+ `osd_boot_logo_template_288x72.png`) | personalization |
| `v_osd_design.py` | P2 OSD design and profiles | personalization |
| `v_lua_widget.py` | P3 EdgeTX Lua widget | personalization |

Each video module defines `SCENES = [(name, fn, seconds)]`; a scene is `fn(t, dur) -> PIL.Image`.
Facts used in each video are listed in the module docstring together with the source they were checked against.
Course modules that go deeper on each topic: see `docs/COURSE-PLAN-TUNING.md`.
