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
