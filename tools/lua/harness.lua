-- Test harness for LinkBox (tools/lua/LinkBox/main.lua) on desktop Lua 5.3.
-- Stubs the EdgeTX globals the widget uses and replays a short flight:
-- no sensors -> link up (6S) -> LQ drops -> hidden (background) -> link lost -> reconnect with a 4S pack.
-- Usage: lua5.3 harness.lua /path/to/LinkBox/main.lua
-- Instruction counts include only code from main.lua (stubs here are Lua, on the radio they are C).

local path = arg[1] or "main.lua"

-- flags: sizes in low bits, colours as index << 16 (like COLOR2FLAGS)
SMLSIZE, MIDSIZE, DBLSIZE, BOLD, RIGHT, BLINK = 0x01, 0x02, 0x04, 0x08, 0x10, 0x20
local CNAMES = { "WHITE", "GREY", "GREEN", "YELLOW", "RED" }
for i, n in ipairs(CNAMES) do _G[n] = i << 16 end
VALUE, COLOR = 0, 7
EVT_VIRTUAL_ENTER, EVT_TOUCH_TAP = 98, 99

local function fmtFlags(f)
  local s = {}
  if f & SMLSIZE ~= 0 then s[#s + 1] = "SML" end
  if f & MIDSIZE ~= 0 then s[#s + 1] = "MID" end
  if f & DBLSIZE ~= 0 then s[#s + 1] = "DBL" end
  if f & BOLD ~= 0 then s[#s + 1] = "BOLD" end
  if f & RIGHT ~= 0 then s[#s + 1] = "RIGHT" end
  if f & BLINK ~= 0 then s[#s + 1] = "BLINK" end
  local c = f >> 16
  s[#s + 1] = CNAMES[c] or "?"
  return table.concat(s, "|")
end

local out = {}
lcd = {
  drawText = function(x, y, t, f) out[#out + 1] = string.format("  text   (%3d,%3d) %-7s %s", x, y, fmtFlags(f or 0), t) end,
  drawNumber = function(x, y, v, f)
    -- like luaL_checkinteger: 16.0 is accepted, 16.4 is an error
    v = assert(math.tointeger(v), "number has no integer representation")
    out[#out + 1] = string.format("  number (%3d,%3d) %-7s %d", x, y, fmtFlags(f or 0), v)
  end,
}

-- telemetry model: sensors[name] = { id, value, current }; discovered = sensor list visible
local now = 0
local sensors = {}
local nextId = 200
function getTime() return now end
function getFieldInfo(name)
  local s = sensors[name]
  if s then return { id = s.id, name = name } end
  return nil
end
local byId = {}
function getSourceValue(id)
  local s = byId[id]
  if not s then return end
  return s.value, s.current, s.current
end
function getValue(id) local s = byId[id]; return (s and s.current) and s.value or 0 end

local function discover(name, value)
  nextId = nextId + 3
  sensors[name] = { id = nextId, value = value, current = true }
  byId[nextId] = sensors[name]
end
local function set(tbl) for k, v in pairs(tbl) do sensors[k].value = v; sensors[k].current = true end end
local function lose() for _, s in pairs(sensors) do s.current = false end end

-- load widget
local chunk = assert(loadfile(path))
local W = chunk()
assert(type(W) == "table" and W.name and W.create and type(W.options) == "table", "widget table incomplete")
print(string.format("widget '%s': %d options, keys create/update/refresh/background = %s/%s/%s/%s",
  W.name, #W.options, tostring(W.create ~= nil), tostring(W.update ~= nil),
  tostring(W.refresh ~= nil), tostring(W.background ~= nil)))

local opts = {}
for _, o in ipairs(W.options) do opts[o[1]] = o[3] end
local zone = { x = 0, y = 0, w = 225, h = 122, xabs = 10, yabs = 40 }
local w = W.create(zone, opts)

local maxInstr = 0
local function counted(fn, ...)
  local count = 0
  debug.sethook(function()
    local src = debug.getinfo(2, "S").source
    if src == "@" .. path then count = count + 1 end
  end, "", 1)
  fn(...)
  debug.sethook()
  return count
end
local function frame(title, event)
  out = {}
  local count = counted(W.refresh, w, event, nil)
  if count > maxInstr then maxInstr = count end
  print(string.format("t=%5.1f s  %s  [%d VM instructions]", now / 100, title, count))
  for _, l in ipairs(out) do print(l) end
end

frame("1. sensors not discovered yet")

now = 150
discover("RQly", 100); discover("RxBt", 24.6); discover("FM", "ACRO")
discover("1RSS", -63); discover("RSNR", 9); discover("TPWR", 250)
frame("2. link up, 6S pack at 24.6 V")

now = 400; set({ RQly = 62, RxBt = 22.1, ["1RSS"] = -96, RSNR = 1, TPWR = 500 })
frame("3. LQ 62 (between LQcrit 50 and LQwarn 80)")

now = 450; set({ RQly = 38, ["1RSS"] = -104, RSNR = -4, TPWR = 1000, FM = "ANGL" })
frame("4. LQ 38 (below LQcrit)")

now = 460; set({ RQly = 41, RxBt = 21.9 })
out = {}
local bgCount = counted(W.background, w)
print(string.format("t=%5.1f s  5. widget hidden: background() samples, %d draw calls  [%d VM instructions]",
  now / 100, #out, bgCount))
now = 470; lose()
now = 970
frame("6. link lost 5 s ago: last good values (from background), grey")

now = 1500; set({ RQly = 100, RxBt = 16.4, FM = "ACRO*", ["1RSS"] = -55, RSNR = 10, TPWR = 25 })
frame("7. reconnect with a fresh 4S pack (cell count re-detected)")

now = 1510
frame("8. full screen, ENTER pressed: LQ minimum reset", EVT_VIRTUAL_ENTER)

W.update(w, { Cells = opts.Cells, LQwarn = opts.LQwarn, LQcrit = opts.LQcrit, Text = opts.Text })
now = 1520; set({ RxBt = 12.9 })
frame("9. update() (zone or option change) under load keeps the latched 4S")

now = 1530; lose(); frame("10. pack swapped: link lost")
now = 1600; set({ RQly = 100, RxBt = 21.0 })
frame("11. auto count trap: 6S at 3.50 V/cell reads as 5S")

opts.Cells = 6; W.update(w, opts)
now = 1610
frame("12. Cells option = 6: correct per-cell value")

set({ RxBt = 3.9 })
now = 1620
frame("13. FC sends average per cell, 0.1 V steps (report_cell_voltage = ON)")

local small = W.create({ x = 0, y = 0, w = 70, h = 36, xabs = 300, yabs = 0 }, opts)
out = {}
W.refresh(small, nil, nil)
print("t= 16.2 s  14. topbar-size zone 70x36")
for _, l in ipairs(out) do print(l) end

print(string.format("max main.lua VM instructions per refresh: %d of the ~20000 widget budget (%.1f %%)",
  maxInstr, maxInstr / 20000 * 100))
