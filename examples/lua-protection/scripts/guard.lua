-- guard.lua — protection pack for ArduPilot Copter (project #11 starter)
--  1. vibration guard: sustained vibration above GRD_VIBE_MAX for GRD_VIBE_S seconds -> LAND
--  2. polygon keep-in: position outside the polygon (inclusive of a GRD_POLY_M margin) -> RTL
--  3. self-protection: any Lua error is caught; after 3 consecutive errors while armed -> RTL
-- Native protections (FENCE_*, FS_*) stay configured: this script adds to them, never replaces them.

local PARAM_KEY, PREFIX = 72, "GRD_"
assert(param:add_table(PARAM_KEY, PREFIX, 4), "could not add param table")
assert(param:add_param(PARAM_KEY, 1, "ENABLE", 1), "ENABLE")
assert(param:add_param(PARAM_KEY, 2, "VIBE_MAX", 30), "VIBE_MAX")   -- m/s/s, same scale as VIBE log
assert(param:add_param(PARAM_KEY, 3, "VIBE_S", 2), "VIBE_S")       -- seconds above the limit
assert(param:add_param(PARAM_KEY, 4, "POLY_M", 10), "POLY_M")      -- margin inside the polygon, m

local MODE_RTL, MODE_LAND = 6, 9
local PERIOD_MS = 100
local MAV_SEVERITY_CRITICAL, MAV_SEVERITY_INFO = 2, 6

-- keep-in polygon (lat, lon in degrees); replace with your site, or load from a file on the SD card
local POLY = {
  {-35.36230, 149.16400}, {-35.36230, 149.16800}, {-35.36500, 149.16800}, {-35.36500, 149.16400},
}

local vibe_since = nil
local acted = false
local errors = 0

local function now_s() return millis():tofloat() * 0.001 end

local function to_ne(lat, lon, lat0, lon0)
  local R = 6378137.0
  return math.rad(lat - lat0) * R, math.rad(lon - lon0) * R * math.cos(math.rad(lat0))
end

-- signed distance to the polygon edge in metres: > 0 inside, < 0 outside
local function poly_distance(lat, lon)
  local inside, dmin = false, math.huge
  local lat0, lon0 = POLY[1][1], POLY[1][2]
  local px, py = to_ne(lat, lon, lat0, lon0)
  local n = #POLY
  for i = 1, n do
    local ax, ay = to_ne(POLY[i][1], POLY[i][2], lat0, lon0)
    local j = i % n + 1
    local bx, by = to_ne(POLY[j][1], POLY[j][2], lat0, lon0)
    if ((ay > py) ~= (by > py)) and (px < (bx - ax) * (py - ay) / (by - ay) + ax) then inside = not inside end
    local dx, dy = bx - ax, by - ay
    local t = math.max(0, math.min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    local ex, ey = px - (ax + t * dx), py - (ay + t * dy)
    dmin = math.min(dmin, math.sqrt(ex * ex + ey * ey))
  end
  return inside and dmin or -dmin
end

local function act(mode, why)
  if acted then return end
  acted = true
  gcs:send_text(MAV_SEVERITY_CRITICAL, "GRD: " .. why)
  if not vehicle:set_mode(mode) then gcs:send_text(MAV_SEVERITY_CRITICAL, "GRD: mode change refused") end
end

local function update()
  if param:get(PREFIX .. "ENABLE") ~= 1 then return end
  if not arming:is_armed() then
    vibe_since, acted = nil, false   -- re-arm the guard for the next flight
    return
  end
  local t = now_s()

  local v = ahrs:get_vibration()
  local vmax = math.max(v:x(), v:y(), v:z())
  if vmax > param:get(PREFIX .. "VIBE_MAX") then
    vibe_since = vibe_since or t
    if t - vibe_since >= param:get(PREFIX .. "VIBE_S") then act(MODE_LAND, string.format("vibration %.0f, LAND", vmax)) end
  else
    vibe_since = nil
  end

  local loc = ahrs:get_location()
  if loc then
    local d = poly_distance(loc:lat() * 1e-7, loc:lng() * 1e-7)
    if d < param:get(PREFIX .. "POLY_M") then act(MODE_RTL, string.format("polygon margin %.0f m, RTL", d)) end
  end
  logger:write("GRD", "Vib,Poly,Act", "ffB", vmax, loc and poly_distance(loc:lat() * 1e-7, loc:lng() * 1e-7) or 0, acted and 1 or 0)
end

local function protected()
  local ok, err = pcall(update)
  if ok then
    errors = 0
  else
    errors = errors + 1
    gcs:send_text(MAV_SEVERITY_CRITICAL, "GRD error: " .. tostring(err))
    if errors >= 3 and arming:is_armed() then act(MODE_RTL, "script failing, RTL") end
  end
  return protected, PERIOD_MS
end

gcs:send_text(MAV_SEVERITY_INFO, "GRD loaded")
return protected, PERIOD_MS
