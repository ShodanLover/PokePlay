-- PokePlay bridge for mGBA 0.10+
--
-- Load this in mGBA with: Tools > Scripting... > File > Load script...
-- It opens a small text server on 127.0.0.1:8888 that the Python agent
-- connects to. The agent uses it to read game memory and press buttons.
--
-- Protocol: one command per line, one reply per line.
--   PING                      -> OK PONG
--   INFO                      -> OK <gamecode> <title>
--   FRAME                     -> OK <frame number>
--   READ <hexaddr> <len>      -> OK <hex bytes>
--   PRESS <keys> <hold> <wait>-> OK   (sent after hold+wait frames have passed)
--        keys: A,B,SELECT,START,RIGHT,LEFT,UP,DOWN,R,L joined with "+", or NONE
--   SCREENSHOT <path>         -> OK
--   SAVESTATE <slot>          -> OK
--   LOADSTATE <slot>          -> OK
-- Errors come back as: ERR <message>

local PORT = 8888

local KEY_BITS = {
  A = 0, B = 1, SELECT = 2, START = 3, RIGHT = 4,
  LEFT = 5, UP = 6, DOWN = 7, R = 8, L = 9,
}

local server = nil
local clients = {}   -- id -> {sock, inbuf, outbuf, jobs}
local nextId = 1

local function keyMask(spec)
  if spec == "NONE" then return 0 end
  local mask = 0
  for name in string.gmatch(spec, "[^+]+") do
    local bit = KEY_BITS[string.upper(name)]
    if bit == nil then return nil, "unknown key " .. name end
    mask = mask | (1 << bit)
  end
  return mask
end

local function toHex(s)
  return (s:gsub(".", function(c) return string.format("%02x", c:byte()) end))
end

local function flush(client)
  while #client.outbuf > 0 do
    local sent, err = client.sock:send(client.outbuf)
    if sent == nil then
      if err ~= socket.ERRORS.AGAIN then
        console:error("PokePlay: send failed: " .. tostring(err))
        client.outbuf = ""
      end
      return
    end
    if sent >= #client.outbuf then
      client.outbuf = ""
    else
      client.outbuf = client.outbuf:sub(sent + 1)
    end
  end
end

local function reply(client, text)
  client.outbuf = client.outbuf .. text .. "\n"
  flush(client)
end

local function handleCommand(client, line)
  local parts = {}
  for w in string.gmatch(line, "%S+") do parts[#parts + 1] = w end
  local cmd = parts[1] and string.upper(parts[1]) or ""

  if cmd == "PING" then
    reply(client, "OK PONG")
  elseif cmd == "INFO" then
    reply(client, "OK " .. tostring(emu:getGameCode()) .. " " .. tostring(emu:getGameTitle()))
  elseif cmd == "FRAME" then
    reply(client, "OK " .. tostring(emu:currentFrame()))
  elseif cmd == "READ" then
    local addr = tonumber(parts[2] or "", 16)
    local len = tonumber(parts[3] or "")
    if addr == nil or len == nil or len < 0 or len > 0x20000 then
      reply(client, "ERR bad READ arguments")
      return
    end
    reply(client, "OK " .. toHex(emu:readRange(addr, len)))
  elseif cmd == "PRESS" then
    local mask, err = keyMask(parts[2] or "NONE")
    local hold = tonumber(parts[3] or "6")
    local wait = tonumber(parts[4] or "6")
    if mask == nil or hold == nil or wait == nil then
      reply(client, "ERR " .. (err or "bad PRESS arguments"))
      return
    end
    -- Queue the press; it is applied frame by frame in onFrame().
    table.insert(client.jobs, { mask = mask, hold = hold, wait = wait, started = false })
  elseif cmd == "SCREENSHOT" then
    emu:screenshot(parts[2])
    reply(client, "OK")
  elseif cmd == "SAVESTATE" then
    emu:saveStateSlot(tonumber(parts[2] or "1"))
    reply(client, "OK")
  elseif cmd == "LOADSTATE" then
    emu:loadStateSlot(tonumber(parts[2] or "1"))
    reply(client, "OK")
  else
    reply(client, "ERR unknown command " .. cmd)
  end
end

local function stopClient(id)
  local client = clients[id]
  if client == nil then return end
  -- Release any keys this client was holding.
  local job = client.jobs[1]
  if job and job.started and job.hold > 0 then emu:clearKeys(job.mask) end
  clients[id] = nil
  client.sock:close()
  console:log("PokePlay: agent " .. id .. " disconnected")
end

local function onReceived(id)
  local client = clients[id]
  if client == nil then return end
  while true do
    local data, err = client.sock:receive(4096)
    if data then
      client.inbuf = client.inbuf .. data
      while true do
        local nl = client.inbuf:find("\n", 1, true)
        if nl == nil then break end
        local line = client.inbuf:sub(1, nl - 1):gsub("\r$", "")
        client.inbuf = client.inbuf:sub(nl + 1)
        if #line > 0 then
          local ok, perr = pcall(handleCommand, client, line)
          if not ok then reply(client, "ERR " .. tostring(perr)) end
        end
      end
    else
      if err ~= socket.ERRORS.AGAIN then stopClient(id) end
      return
    end
  end
end

local function onAccept()
  local sock, err = server:accept()
  if err then
    console:error("PokePlay: accept failed: " .. tostring(err))
    return
  end
  local id = nextId
  nextId = nextId + 1
  clients[id] = { sock = sock, inbuf = "", outbuf = "", jobs = {} }
  sock:add("received", function() onReceived(id) end)
  sock:add("error", function() stopClient(id) end)
  console:log("PokePlay: agent " .. id .. " connected")
end

-- Advance queued button presses one frame at a time.
local function onFrame()
  for _, client in pairs(clients) do
    local job = client.jobs[1]
    if job then
      if not job.started then
        job.started = true
        if job.hold > 0 and job.mask ~= 0 then emu:addKeys(job.mask) end
      end
      if job.hold > 0 then
        job.hold = job.hold - 1
        if job.hold == 0 and job.mask ~= 0 then emu:clearKeys(job.mask) end
      elseif job.wait > 0 then
        job.wait = job.wait - 1
      end
      if job.hold == 0 and job.wait == 0 then
        table.remove(client.jobs, 1)
        reply(client, "OK")
      end
    end
    if #client.outbuf > 0 then flush(client) end
  end
end

callbacks:add("frame", onFrame)

local err
server, err = socket.bind("127.0.0.1", PORT)
if err then
  console:error("PokePlay: could not open port " .. PORT .. ": " .. tostring(err))
else
  local ok
  ok, err = server:listen()
  if err then
    server:close()
    console:error("PokePlay: listen failed: " .. tostring(err))
  else
    server:add("received", onAccept)
    console:log("PokePlay bridge listening on 127.0.0.1:" .. PORT .. " - now start the Python agent.")
  end
end
