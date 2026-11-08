// Her pixel-art avatar (original design). Draws on a <canvas id="avatar"> and animates from /state.json.
// Frames are 32x32; each letter is a palette color, "." is transparent.
const AVATAR_PALETTE = {"K": "#181028", "H": "#ff46aa", "h": "#c8288c", "L": "#ff96d2", "S": "#ffd6ba", "s": "#e8aa96", "W": "#ffffff", "P": "#28f0e6", "p": "#1496aa", "M": "#781e3c", "m": "#e65a6e", "B": "#ff8ca0", "C": "#32325a", "c": "#222240", "G": "#5a5a6e", "g": "#9696aa", "Y": "#3cffc8", "T": "#ffe650"};
const AVATAR_FRAMES = {
"idle": [
"............KKKKKKHH............",
".........KKKgggggKggHKK.........",
".......KKgggHHHHHHHHgggKK.......",
"......KggLHHHHHHHHHHHHLggK......",
"......gHLHHHHHHHHHHHHHHLHg......",
"...g.KHHHHhHHHHHHHHHHhHHHHK.g...",
"...g.KHHHhHHHHHHHHHHHHhHHHK.g...",
"...gKHHHhHHHHHHHHHHHHHHhHHHKg...",
"...gKHHhHHHhHHHHHHHHhHHHhHHKg...",
"...gHHhHHHhSHHHhhHHHShHHHhHHg...",
".KKKKHhHHhSSShSSSShSSShHHhHKKKK.",
".KGGKHhHhSSSSSSSSSSSSSShHhHKGGK.",
".KYGKHhHSKKKKSSSSSSKKKKSHhHKGYK.",
".KYGKHhHKWPPKSSSSSSKPPWKHhHKGYK.",
".KGGKhHHKPWpKSSSSSSKpWPKHHhKGGK.",
".KKKKgHHSKKKKSSSSSSKKKKSHHhKKKK.",
"...KHhgHSBBSSSSSSSSSSBBSHHhHK...",
"...KHhhgGYSSSSKKKKSSSSSSHhhHK...",
"...KHHhHKSSSSSSSSSSSSSSKHhHHK...",
"....KHhHHKSSSSSSSSSSSSKHHhHK....",
"....KHHhHHKKSSSSSSSSKKHHhHHK....",
"....KHHhHHHHKssssssKHHHHhHHK....",
"...KHHhhHHHKCssssssCKHHHhhHHK...",
"...KHHhKCCCCCCcsscCCCCCCKhHHK...",
"..KHHhKCCCCCCCCCCCCCCCCCCKhHHK..",
"..KHhKCCCCCCCCCCCCCCCCCCCCKhHK..",
"..KHKCCCCCcCCCCCCCCCCcCCCCCKHK..",
"..KKCCCCCCcCCCYCCYCCCcCCCCCCKK..",
"..KCCCCCCCcCCCCCCCCCCcCCCCCCCK..",
"..KCCCCCCCcCCCCCCCCCCcCCCCCCCK..",
"..KCCCCCCCcCCCCCCCCCCcCCCCCCCK..",
"..KKKKKKKKKKKKKKKKKKKKKKKKKKKK.."
],
"talk": [
"............KKKKKKHH............",
".........KKKgggggKggHKK.........",
".......KKgggHHHHHHHHgggKK.......",
"......KggLHHHHHHHHHHHHLggK......",
"......gHLHHHHHHHHHHHHHHLHg......",
"...g.KHHHHhHHHHHHHHHHhHHHHK.g...",
"...g.KHHHhHHHHHHHHHHHHhHHHK.g...",
"...gKHHHhHHHHHHHHHHHHHHhHHHKg...",
"...gKHHhHHHhHHHHHHHHhHHHhHHKg...",
"...gHHhHHHhSHHHhhHHHShHHHhHHg...",
".KKKKHhHHhSSShSSSShSSShHHhHKKKK.",
".KGGKHhHhSSSSSSSSSSSSSShHhHKGGK.",
".KYGKHhHSKKKKSSSSSSKKKKSHhHKGYK.",
".KYGKHhHKWPPKSSSSSSKPPWKHhHKGYK.",
".KGGKhHHKPWpKSSSSSSKpWPKHHhKGGK.",
".KKKKgHHSKKKKSSSSSSKKKKSHHhKKKK.",
"...KHhgHSBBSSSSSSSSSSBBSHHhHK...",
"...KHhhgGYSSSSKMMKSSSSSSHhhHK...",
"...KHHhHKSSSSSKmmKSSSSSKHhHHK...",
"....KHhHHKSSSSSKKSSSSSKHHhHK....",
"....KHHhHHKKSSSSSSSSKKHHhHHK....",
"....KHHhHHHHKssssssKHHHHhHHK....",
"...KHHhhHHHKCssssssCKHHHhhHHK...",
"...KHHhKCCCCCCcsscCCCCCCKhHHK...",
"..KHHhKCCCCCCCCCCCCCCCCCCKhHHK..",
"..KHhKCCCCCCCCCCCCCCCCCCCCKhHK..",
"..KHKCCCCCcCCCCCCCCCCcCCCCCKHK..",
"..KKCCCCCCcCCCYCCYCCCcCCCCCCKK..",
"..KCCCCCCCcCCCCCCCCCCcCCCCCCCK..",
"..KCCCCCCCcCCCCCCCCCCcCCCCCCCK..",
"..KCCCCCCCcCCCCCCCCCCcCCCCCCCK..",
"..KKKKKKKKKKKKKKKKKKKKKKKKKKKK.."
],
"blink": [
"............KKKKKKHH............",
".........KKKgggggKggHKK.........",
".......KKgggHHHHHHHHgggKK.......",
"......KggLHHHHHHHHHHHHLggK......",
"......gHLHHHHHHHHHHHHHHLHg......",
"...g.KHHHHhHHHHHHHHHHhHHHHK.g...",
"...g.KHHHhHHHHHHHHHHHHhHHHK.g...",
"...gKHHHhHHHHHHHHHHHHHHhHHHKg...",
"...gKHHhHHHhHHHHHHHHhHHHhHHKg...",
"...gHHhHHHhSHHHhhHHHShHHHhHHg...",
".KKKKHhHHhSSShSSSShSSShHHhHKKKK.",
".KGGKHhHhSSSSSSSSSSSSSShHhHKGGK.",
".KYGKHhHSSSSSSSSSSSSSSSSHhHKGYK.",
".KYGKHhHSSSSSSSSSSSSSSSSHhHKGYK.",
".KGGKhHHKKKKKSSSSSSKKKKKHHhKGGK.",
".KKKKgHHSSSSSSSSSSSSSSSSHHhKKKK.",
"...KHhgHSBBSSSSSSSSSSBBSHHhHK...",
"...KHhhgGYSSSSKKKKSSSSSSHhhHK...",
"...KHHhHKSSSSSSSSSSSSSSKHhHHK...",
"....KHhHHKSSSSSSSSSSSSKHHhHK....",
"....KHHhHHKKSSSSSSSSKKHHhHHK....",
"....KHHhHHHHKssssssKHHHHhHHK....",
"...KHHhhHHHKCssssssCKHHHhhHHK...",
"...KHHhKCCCCCCcsscCCCCCCKhHHK...",
"..KHHhKCCCCCCCCCCCCCCCCCCKhHHK..",
"..KHhKCCCCCCCCCCCCCCCCCCCCKhHK..",
"..KHKCCCCCcCCCCCCCCCCcCCCCCKHK..",
"..KKCCCCCCcCCCYCCYCCCcCCCCCCKK..",
"..KCCCCCCCcCCCCCCCCCCcCCCCCCCK..",
"..KCCCCCCCcCCCCCCCCCCcCCCCCCCK..",
"..KCCCCCCCcCCCCCCCCCCcCCCCCCCK..",
"..KKKKKKKKKKKKKKKKKKKKKKKKKKKK.."
],
"grin": [
"............KKKKKKHH............",
".........KKKgggggKggHKK.........",
".......KKgggHHHHHHHHgggKK.......",
"......KggLHHHHHHHHHHHHLggK......",
"......gHLHHHHHHHHHHHHHHLHg......",
"...g.KHHHHhHHHHHHHHHHhHHHHK.g...",
"...g.KHHHhHHHHHHHHHHHHhHHHK.g...",
"...gKHHHhHHHHHHHHHHHHHHhHHHKg...",
"...gKHHhHHHhHHHHHHHHhHHHhHHKg...",
"...gHHhHHHhSHHHhhHHHShHHHhHHg...",
".KKKKHhHHhSSShSSSShSSShHHhHKKKK.",
".KGGKHhHhSSSSSSSSSSSSSShHhHKGGK.",
".KYGKHhHSKKKKSSSSSSKKKKSHhHKGYK.",
".KYGKHhHKWPPKSSSSSSKPPWKHhHKGYK.",
".KGGKhHHKPWpKSSSSSSKpWPKHHhKGGK.",
".KKKKgHHSKKKKSSSSSSKKKKSHHhKKKK.",
"...KHhgHSBBSSSSSSSSSSBBSHHhHK...",
"...KHhhgGYSSSKWWWWKSSSSSHhhHK...",
"...KHHhHKSSSSSKKKKSSSSSKHhHHK...",
"....KHhHHKSSSSSSSSSSSSKHHhHK....",
"....KHHhHHKKSSSSSSSSKKHHhHHK....",
"....KHHhHHHHKssssssKHHHHhHHK....",
"...KHHhhHHHKCssssssCKHHHhhHHK...",
"...KHHhKCCCCCCcsscCCCCCCKhHHK...",
"..KHHhKCCCCCCCCCCCCCCCCCCKhHHK..",
"..KHhKCCCCCCCCCCCCCCCCCCCCKhHK..",
"..KHKCCCCCcCCCCCCCCCCcCCCCCKHK..",
"..KKCCCCCCcCCCYCCYCCCcCCCCCCKK..",
"..KCCCCCCCcCCCCCCCCCCcCCCCCCCK..",
"..KCCCCCCCcCCCCCCCCCCcCCCCCCCK..",
"..KCCCCCCCcCCCCCCCCCCcCCCCCCCK..",
"..KKKKKKKKKKKKKKKKKKKKKKKKKKKK.."
]
};
const HAPPY_WORDS = /(happy|excit|hype|joy|thrill|giddy|ecstat|great|proud|delight|smug|chaotic|manic|unhinged|gleeful)/i;

function startAvatar(canvas, opts = {}) {
  const ctx = canvas.getContext("2d");
  const scale = canvas.width / 32;
  let talking = false, mood = "", thinking = false, blinkUntil = 0, nextBlink = performance.now() + 3000;
  let glitchUntil = 0, nextGlitch = performance.now() + 12000 + Math.random() * 20000;

  function draw(name, offsetX = 0, tint = null) {
    const rows = AVATAR_FRAMES[name];
    for (let y = 0; y < 32; y++) for (let x = 0; x < 32; x++) {
      const c = rows[y][x];
      if (c === ".") continue;
      ctx.fillStyle = tint || AVATAR_PALETTE[c];
      ctx.fillRect((x + offsetX) * scale, y * scale, scale, scale);
    }
  }

  function frame(now) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (now > nextBlink) { blinkUntil = now + 140; nextBlink = now + 2500 + Math.random() * 3500; }
    let name = HAPPY_WORDS.test(mood) ? "grin" : "idle";
    if (talking) name = Math.floor(now / 130) % 2 ? "talk" : (name === "grin" ? "grin" : "idle");
    if (now < blinkUntil) name = "blink";
    // Occasional glitch: she's a little unhinged.
    if (now > nextGlitch) { glitchUntil = now + 350; nextGlitch = now + 15000 + Math.random() * 25000; }
    if (now < glitchUntil) {
      ctx.globalAlpha = 0.6; draw(name, -1, "#ff2bd6"); draw(name, 1, "#20f0ff"); ctx.globalAlpha = 1;
      canvas.style.transform = `translate(${(Math.random() - 0.5) * 6}px, 0)`;
    } else {
      // gentle idle bob
      canvas.style.transform = `translateY(${Math.sin(now / 600) * 2}px)`;
    }
    draw(name);
    if (opts.bubble) opts.bubble.style.opacity = thinking ? 1 : 0;
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);

  async function poll() {
    try {
      const s = await (await fetch("/state.json", { cache: "no-store" })).json();
      talking = !!s.subtitle;
      mood = s.mood || "";
      thinking = !talking && (s.thought || "").startsWith("Thinking");
      if (opts.nameTag && s.streamer) opts.nameTag.textContent = s.streamer;
    } catch (e) {}
  }
  setInterval(poll, 150);
}
