// Her 3D avatar: an original character built entirely in code, with no outside models or art.
// It reads /state.json like the rest of the overlay. Talking, thinking, moods and boss fights all change how she looks.
function startAvatar3D(canvas, opts = {}) {
  const SIZE = 280, FRAME_MS = 32;
  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
  renderer.setPixelRatio(2);
  renderer.setSize(SIZE, SIZE, false);
  renderer.setClearColor(0x000000, 0);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(24, 1, 0.1, 50);
  camera.position.set(0, 0.05, 9.6);
  camera.lookAt(0, -0.08, 0);

  scene.add(new THREE.HemisphereLight(0xfff1fa, 0x38306a, 0.95));
  const key = new THREE.DirectionalLight(0xffffff, 1.9); key.position.set(-4, 3.5, 4.5); scene.add(key);
  const rimPink = new THREE.DirectionalLight(0xff4fb0, 2.2); rimPink.position.set(-5, 1, -3); scene.add(rimPink);
  const rimCyan = new THREE.DirectionalLight(0x35e8ff, 2.2); rimCyan.position.set(5, 2, -3); scene.add(rimCyan);

  const ramp = new THREE.DataTexture(new Uint8Array([120, 190, 255]), 3, 1, THREE.RedFormat);
  ramp.minFilter = ramp.magFilter = THREE.NearestFilter;
  ramp.needsUpdate = true;
  const toon = (color, extra = {}) => new THREE.MeshToonMaterial({ color, gradientMap: ramp, ...extra });

  const ink = new THREE.MeshBasicMaterial({ color: 0x17102a, side: THREE.BackSide });
  ink.onBeforeCompile = shader => {
    shader.vertexShader = shader.vertexShader.replace("#include <begin_vertex>",
      "#include <begin_vertex>\n transformed += normalize(normal) * 0.024;");
  };
  function part(geometry, material, parent, inked = true) {
    const mesh = new THREE.Mesh(geometry, material);
    if (inked) mesh.add(new THREE.Mesh(geometry, ink));
    parent.add(mesh);
    return mesh;
  }

  // A strand of hair: a tube that tapers to a point, pink at the root and cyan at the tip.
  const ROOT_COLOR = new THREE.Color(0xff4fae), TIP_COLOR = new THREE.Color(0x3de4ff);
  function strand(points, width, flat = 0.55) {
    const curve = new THREE.CatmullRomCurve3(points);
    const rows = 22, sides = 8, frames = curve.computeFrenetFrames(rows, false);
    const position = [], normal = [], color = [], index = [];
    const p = new THREE.Vector3(), n = new THREE.Vector3(), c = new THREE.Color();
    for (let i = 0; i <= rows; i++) {
      const t = i / rows;
      curve.getPointAt(t, p);
      const r = width * Math.pow(1 - t, 0.7) * (0.55 + 0.45 * Math.min(1, t * 5)) + 0.002;
      const blend = Math.min(1, Math.max(0, (t - 0.55) / 0.45));
      c.copy(ROOT_COLOR).lerp(TIP_COLOR, blend * blend);
      for (let j = 0; j <= sides; j++) {
        const a = (j / sides) * Math.PI * 2, ca = Math.cos(a), sa = Math.sin(a);
        n.copy(frames.normals[i]).multiplyScalar(ca * r).addScaledVector(frames.binormals[i], sa * r * flat).add(p);
        position.push(n.x, n.y, n.z);
        n.copy(frames.normals[i]).multiplyScalar(ca).addScaledVector(frames.binormals[i], sa / flat).normalize();
        normal.push(n.x, n.y, n.z);
        color.push(c.r, c.g, c.b);
      }
    }
    for (let i = 0; i < rows; i++) for (let j = 0; j < sides; j++) {
      const a = i * (sides + 1) + j, b = a + sides + 1;
      index.push(a, a + 1, b, b, a + 1, b + 1);
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(position, 3));
    geometry.setAttribute("normal", new THREE.Float32BufferAttribute(normal, 3));
    geometry.setAttribute("color", new THREE.Float32BufferAttribute(color, 3));
    geometry.setIndex(index);
    return geometry;
  }

  const hairMat = toon(0xffffff, { vertexColors: true });
  const capMat = toon(0xff4fae);
  const swaying = [];
  function addStrand(parent, points, width, swing, flat) {
    const root = points[0].clone();
    const group = new THREE.Group();
    group.position.copy(root);
    parent.add(group);
    part(strand(points.map(v => v.clone().sub(root)), width, flat), hairMat, group);
    swaying.push({ group, swing, phase: Math.random() * 6.28 });
    return group;
  }
  const v = (x, y, z) => new THREE.Vector3(x, y, z);

  // Everything hangs off this, so she can hop and spin as one.
  const root = new THREE.Group(); scene.add(root);

  // ------------------------------------------------------------ the glowing rings and sparks behind her
  const ringColor = new THREE.Color(0xff4fae), accentColor = new THREE.Color(0x3de4ff);
  const ringMat = new THREE.MeshBasicMaterial({ color: ringColor });
  const accentMat = new THREE.MeshBasicMaterial({ color: accentColor });
  const rings = new THREE.Group(); rings.position.set(0, 0.15, -1.5); rings.rotation.x = 0.22; scene.add(rings);
  rings.add(new THREE.Mesh(new THREE.TorusGeometry(2.0, 0.02, 8, 96), ringMat));
  const arcs = new THREE.Group(); rings.add(arcs);
  for (let i = 0; i < 3; i++) {
    const arc = new THREE.Mesh(new THREE.TorusGeometry(1.78, 0.04, 8, 40, 1.35), accentMat);
    arc.rotation.z = (i / 3) * Math.PI * 2;
    arcs.add(arc);
  }
  function softDot() {
    const c = document.createElement("canvas"); c.width = c.height = 128;
    const x = c.getContext("2d"), g = x.createRadialGradient(64, 64, 0, 64, 64, 64);
    g.addColorStop(0, "rgba(255,255,255,1)"); g.addColorStop(0.5, "rgba(255,255,255,.35)"); g.addColorStop(1, "rgba(255,255,255,0)");
    x.fillStyle = g; x.fillRect(0, 0, 128, 128);
    return new THREE.CanvasTexture(c);
  }
  const dot = softDot();
  const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: dot, color: ringColor, transparent: true, opacity: 0.42, depthWrite: false }));
  halo.scale.set(5.2, 5.2, 1); halo.position.set(0, 0.3, -2.2); scene.add(halo);
  const SPARKS = 36, sparkPos = new Float32Array(SPARKS * 3), sparkSpeed = [];
  for (let i = 0; i < SPARKS; i++) {
    sparkPos[i * 3] = (Math.random() - 0.5) * 4.2;
    sparkPos[i * 3 + 1] = (Math.random() - 0.5) * 4.4;
    sparkPos[i * 3 + 2] = -1 + Math.random() * 2.2;
    sparkSpeed.push(0.12 + Math.random() * 0.3);
  }
  const sparkGeo = new THREE.BufferGeometry();
  sparkGeo.setAttribute("position", new THREE.BufferAttribute(sparkPos, 3));
  scene.add(new THREE.Points(sparkGeo, new THREE.PointsMaterial({ size: 0.13, map: dot, color: accentColor, transparent: true, depthWrite: false })));

  // ------------------------------------------------------------ body: a dark hoodie
  const body = new THREE.Group(); root.add(body);
  const hoodie = toon(0x2a2c58), hoodieDark = toon(0x1d1e42), skin = toon(0xffc9ad);
  const profile = [[1.3, -3.2], [1.3, -2.1], [1.2, -1.55], [0.96, -1.22], [0.55, -1.02], [0.3, -0.92]].map(([x, y]) => new THREE.Vector2(x, y));
  const torso = new THREE.LatheGeometry(profile, 44); torso.scale(1, 1, 0.72);
  part(torso, hoodie, body);
  part(new THREE.CylinderGeometry(0.2, 0.25, 0.55, 20).translate(0, -0.72, 0), skin, body, false);
  const collar = part(new THREE.TorusGeometry(0.47, 0.17, 12, 36), toon(0xff4fae), body);
  collar.rotation.x = Math.PI / 2; collar.position.set(0, -0.98, 0); collar.scale.set(1, 0.82, 1);
  const hood = part(new THREE.SphereGeometry(0.86, 24, 16), hoodieDark, body);
  hood.position.set(0, -0.92, -0.72); hood.scale.set(1.05, 0.72, 0.62);
  const zip = new THREE.Mesh(new THREE.BoxGeometry(0.035, 1.7, 0.02), new THREE.MeshBasicMaterial({ color: 0x8f93c9 }));
  zip.position.set(0, -2.15, 0.9); body.add(zip);
  for (const side of [-1, 1]) {
    const tube = new THREE.TubeGeometry(new THREE.CatmullRomCurve3([v(side * 0.2, -1.08, 0.5), v(side * 0.27, -1.4, 0.8), v(side * 0.24, -1.72, 0.87)]), 12, 0.022, 6);
    body.add(new THREE.Mesh(tube, new THREE.MeshBasicMaterial({ color: 0xf2f4f8 })));
  }
  const emblem = new THREE.Mesh(new THREE.RingGeometry(0.15, 0.22, 6), accentMat);
  emblem.position.set(0.55, -1.72, 0.83); emblem.rotation.y = 0.5; body.add(emblem);

  // ------------------------------------------------------------ head
  const head = new THREE.Group(); head.position.y = 0.3; root.add(head);
  function shapeHead(geometry) {                    // a rounder top and a narrower chin
    const pos = geometry.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      const y = pos.getY(i), narrow = y < 0 ? 1 - 0.24 * Math.pow(-y, 1.6) : 1;
      pos.setXYZ(i, pos.getX(i) * narrow, y * 0.95, pos.getZ(i) * narrow * 0.95);
    }
    geometry.computeVertexNormals();
    return geometry;
  }
  part(shapeHead(new THREE.SphereGeometry(1, 48, 36)), skin, head);

  const faceCanvas = document.createElement("canvas"); faceCanvas.width = faceCanvas.height = 512;
  const faceTex = new THREE.CanvasTexture(faceCanvas);
  faceTex.colorSpace = THREE.SRGBColorSpace; faceTex.anisotropy = 4;
  const FACE_SPAN = 1.6;
  const faceGeo = shapeHead(new THREE.SphereGeometry(1.006, 32, 24, Math.PI / 2 - FACE_SPAN / 2, FACE_SPAN, Math.PI / 2 - FACE_SPAN / 2, FACE_SPAN));
  head.add(new THREE.Mesh(faceGeo, new THREE.MeshBasicMaterial({ map: faceTex, transparent: true, depthWrite: false })));

  part(new THREE.SphereGeometry(1.06, 40, 20, 0, Math.PI * 2, 0, 1.25).scale(1, 0.98, 0.98), capMat, head);
  part(new THREE.SphereGeometry(1.06, 40, 28, Math.PI / 2 + 1.05, Math.PI * 2 - 2.1, 0, 2.3).scale(1, 0.98, 0.98), capMat, head);
  const shine = new THREE.Mesh(new THREE.SphereGeometry(1.075, 40, 3, Math.PI / 2 - 1, 2, 0.7, 0.09), new THREE.MeshBasicMaterial({ color: 0xffb4e0 }));
  head.add(shine);

  const onHead = (x, y) => Math.sqrt(Math.max(0.03, 1 - x * x - (y * y) / 0.9)) * 0.96 + 0.1;
  for (const [x, tip] of [[-0.86, 0.02], [-0.62, 0.2], [-0.36, 0.14], [-0.12, 0.26], [0.12, 0.18], [0.36, 0.26], [0.62, 0.16], [0.86, 0.04]]) {
    addStrand(head, [v(x * 0.45, 1.0, 0.42), v(x * 0.85, 0.82, onHead(x * 0.85, 0.82)), v(x, 0.55, onHead(x, 0.55)), v(x * 1.04, tip, onHead(x * 1.04, tip))], 0.3, 0.012, 0.5);
  }
  for (const side of [-1, 1]) {
    addStrand(head, [v(side * 0.82, 0.5, 0.42), v(side * 1.08, -0.22, 0.48), v(side * 1.02, -1.0, 0.46), v(side * 0.74, -1.62, 0.6)], 0.34, 0.035, 0.7);
    // Twin tails, tied high at the back.
    addStrand(head, [v(side * 0.8, 0.72, -0.4), v(side * 1.38, 0.72, -0.5), v(side * 1.6, -0.25, -0.5), v(side * 1.48, -1.1, -0.42), v(side * 1.24, -1.9, -0.3)], 0.4, 0.045, 0.85);
    addStrand(head, [v(side * 0.8, 0.66, -0.42), v(side * 1.3, 0.42, -0.62), v(side * 1.48, -0.42, -0.62), v(side * 1.22, -1.45, -0.5)], 0.3, 0.08, 0.8);
    const tie = new THREE.Mesh(new THREE.TorusGeometry(0.17, 0.05, 10, 24), accentMat);
    tie.position.set(side * 0.86, 0.72, -0.41); tie.rotation.y = Math.PI / 2 + side * 0.2; head.add(tie);
  }
  for (const [x, z] of [[-0.8, -0.45], [-0.45, -0.85], [0, -1], [0.45, -0.85], [0.8, -0.45]]) {
    addStrand(head, [v(x * 0.9, 0.2, z * 0.9), v(x * 1.15, -0.7, z * 1.12), v(x * 1.2, -1.5, z * 1.15), v(x * 1.05, -2.3, z * 1.1)], 0.34, 0.03, 0.6);
  }
  const ahoge = addStrand(head, [v(0, 1.0, 0.05), v(0.12, 1.45, 0.1), v(0.42, 1.62, 0.08), v(0.66, 1.36, 0.06)], 0.08, 0.05, 0.7);

  // ------------------------------------------------------------ headset
  const metal = toon(0x34365f), metalDark = toon(0x20213f);
  const band = part(new THREE.TorusGeometry(1.24, 0.085, 12, 56, Math.PI), metal, head);
  band.rotation.x = -0.1;
  for (const side of [-1, 1]) {
    const cup = new THREE.Group(); cup.position.set(side * 1.3, 0.08, 0.02); cup.rotation.z = side * -Math.PI / 2; cup.rotation.x = side * 0.0; head.add(cup);
    part(new THREE.CylinderGeometry(0.36, 0.46, 0.34, 36), metalDark, cup);
    const glow = new THREE.Mesh(new THREE.TorusGeometry(0.27, 0.045, 10, 36), accentMat);
    glow.rotation.x = Math.PI / 2; glow.position.y = 0.185; cup.add(glow);
    const core = new THREE.Mesh(new THREE.CircleGeometry(0.14, 24), ringMat);
    core.rotation.x = -Math.PI / 2; core.position.y = 0.18; cup.add(core);
  }

  // ------------------------------------------------------------ her face, drawn fresh when her expression changes
  const fx = faceCanvas.getContext("2d");
  const INK = "#17102a", BROW = "#b0206f";
  function star(x, y, r) {
    fx.beginPath();
    for (let i = 0; i < 10; i++) {
      const a = -Math.PI / 2 + (i * Math.PI) / 5, d = i % 2 ? r * 0.42 : r;
      fx[i ? "lineTo" : "moveTo"](x + Math.cos(a) * d, y + Math.sin(a) * d);
    }
    fx.closePath(); fx.fillStyle = "#ffd84a"; fx.fill();
    fx.lineWidth = 8; fx.strokeStyle = INK; fx.stroke();
  }
  function eye(cx, side, f) {
    const y = 290;
    fx.lineCap = "round"; fx.strokeStyle = INK; fx.lineWidth = 13;
    if (f.eyes === "x") {
      fx.beginPath(); fx.moveTo(cx - 36, y - 36); fx.lineTo(cx + 36, y + 36); fx.moveTo(cx + 36, y - 36); fx.lineTo(cx - 36, y + 36); fx.stroke();
      return;
    }
    if (f.eyes === "star") { star(cx, y, 62); return; }
    if (f.eyes === "shut") { fx.beginPath(); fx.arc(cx, y + 18, 46, Math.PI * 1.15, Math.PI * 1.85); fx.stroke(); return; }
    fx.save(); fx.translate(cx, y); fx.scale(1.1, f.open * 1.1);
    fx.beginPath(); fx.ellipse(0, 0, 52, 66, 0, 0, Math.PI * 2); fx.fillStyle = "#ffffff"; fx.fill();
    fx.save(); fx.clip();
    const lx = f.lookX, ly = f.lookY, iris = fx.createLinearGradient(0, ly - 54, 0, ly + 54);
    iris.addColorStop(0, "#0b5c78"); iris.addColorStop(0.55, "#16cfe6"); iris.addColorStop(1, "#a4fbff");
    fx.beginPath(); fx.ellipse(lx, ly, 40, 55, 0, 0, Math.PI * 2); fx.fillStyle = iris; fx.fill();
    fx.beginPath(); fx.ellipse(lx, ly + 3, 19, 30, 0, 0, Math.PI * 2); fx.fillStyle = "#0a1230"; fx.fill();
    fx.beginPath(); fx.ellipse(lx - 15, ly - 24, 14, 18, -0.3, 0, Math.PI * 2); fx.fillStyle = "#ffffff"; fx.fill();
    fx.beginPath(); fx.ellipse(lx + 14, ly + 26, 7, 9, 0, 0, Math.PI * 2); fx.fill();
    fx.restore();
    fx.lineWidth = 13;
    fx.beginPath(); fx.ellipse(0, 0, 54, 68, 0, Math.PI * 1.08, Math.PI * 1.92); fx.stroke();
    fx.lineWidth = 8; fx.beginPath(); fx.moveTo(side * 50, -24); fx.lineTo(side * 72, -42); fx.stroke();
    fx.restore();
  }
  function drawFace(f) {
    fx.clearRect(0, 0, 512, 512);
    eye(138, -1, f); eye(374, 1, f);
    const lift = f.brow === "sad" ? 18 : f.brow === "angry" ? -20 : 0;
    fx.strokeStyle = BROW; fx.lineWidth = 11; fx.lineCap = "round";
    fx.beginPath(); fx.moveTo(84, 196); fx.quadraticCurveTo(134, 182 - lift * 0.3, 190, 196 - lift);
    fx.moveTo(428, 196); fx.quadraticCurveTo(378, 182 - lift * 0.3, 322, 196 - lift); fx.stroke();
    fx.fillStyle = "rgba(255,110,160,.5)";
    fx.beginPath(); fx.ellipse(78, 376, 40, 20, 0, 0, Math.PI * 2); fx.ellipse(434, 376, 40, 20, 0, 0, Math.PI * 2); fx.fill();
    fx.strokeStyle = "#d48d80"; fx.lineWidth = 6;
    fx.beginPath(); fx.moveTo(254, 366); fx.lineTo(260, 374); fx.stroke();
    const mx = 256, my = 420;
    fx.strokeStyle = INK; fx.lineWidth = 9;
    if (f.open_mouth > 0.05) {
      const h = 10 + f.open_mouth * 34, w = 22 + f.open_mouth * 12;
      fx.beginPath(); fx.ellipse(mx, my, w, h, 0, 0, Math.PI * 2); fx.fillStyle = "#5c1633"; fx.fill(); fx.stroke();
      fx.save(); fx.beginPath(); fx.ellipse(mx, my, w - 3, h - 3, 0, 0, Math.PI * 2); fx.clip();
      fx.beginPath(); fx.ellipse(mx, my + h * 0.7, w * 0.8, h * 0.6, 0, 0, Math.PI * 2); fx.fillStyle = "#ff7f97"; fx.fill(); fx.restore();
    } else if (f.mouth === "grin") {
      fx.beginPath(); fx.moveTo(mx - 44, my - 8); fx.quadraticCurveTo(mx, my + 46, mx + 44, my - 8); fx.closePath();
      fx.fillStyle = "#ffffff"; fx.fill(); fx.stroke();
    } else if (f.mouth === "sad") {
      fx.beginPath(); fx.arc(mx, my + 34, 34, Math.PI * 1.2, Math.PI * 1.8); fx.stroke();
    } else if (f.mouth === "flat") {
      fx.beginPath(); fx.moveTo(mx - 24, my); fx.lineTo(mx + 24, my + 4); fx.stroke();
    } else {
      fx.beginPath(); fx.moveTo(mx - 28, my - 2); fx.quadraticCurveTo(mx + 2, my + 20, mx + 32, my - 8); fx.stroke();
    }
    faceTex.needsUpdate = true;
  }

  // ------------------------------------------------------------ what's going on, from the bot
  const TONES = { "": [0xff4fae, 0x3de4ff], fight: [0xffcb3d, 0xff7a2e], won: [0x3ddc84, 0xffe066], lost: [0xff5a5f, 0x7a4cff] };
  const HAPPY = /(happy|excit|hype|joy|thrill|giddy|ecstat|great|proud|delight|smug|manic|unhinged|gleeful)/i;
  let talking = false, thinking = false, mood = "", bossState = "";
  async function poll() {
    try {
      const s = await (await fetch("/state.json", { cache: "no-store" })).json();
      talking = !!s.subtitle;
      mood = s.mood || "";
      thinking = !talking && (s.thought || "").startsWith("Thinking");
      const next = s.boss ? s.boss.state : "";
      if (next === "won" && bossState !== "won") celebrateFrom = clock;
      bossState = next;
      if (opts.nameTag && s.streamer) opts.nameTag.textContent = s.streamer;
    } catch (e) { /* the bot isn't running yet */ }
  }
  setInterval(poll, 150);
  poll();

  // ------------------------------------------------------------ animation
  let clock = 0, celebrateFrom = -10, lastFrame = 0, shownFace = "";
  let blinkEnd = 0, nextBlink = 3, glitchEnd = 0, nextGlitch = 14 + Math.random() * 20, gazeX = -10, gazeY = 0, nextGaze = 2;
  let yaw = -0.22, pitch = 0, roll = 0, sink = 0, lastYaw = yaw;
  const targetRing = new THREE.Color(), targetAccent = new THREE.Color();
  const SWAY = { "": 1, fight: 1.6, won: 2, lost: 0.5 };

  function ease(from, to, rate, dt) { return from + (to - from) * Math.min(1, rate * dt); }

  function frame(now) {
    requestAnimationFrame(frame);
    if (now - lastFrame < FRAME_MS) return;
    const dt = Math.min(0.1, (now - lastFrame) / 1000);
    lastFrame = now; clock += dt;
    const t = clock, tone = TONES[bossState] || TONES[""], speed = SWAY[bossState] || 1;

    targetRing.setHex(tone[0]); targetAccent.setHex(tone[1]);
    ringColor.lerp(targetRing, Math.min(1, 5 * dt)); accentColor.lerp(targetAccent, Math.min(1, 5 * dt));
    halo.material.opacity = 0.36 + 0.1 * Math.sin(t * 2.2 * speed) + (bossState ? 0.14 : 0);
    rings.rotation.z += dt * 0.12 * speed;
    arcs.rotation.z -= dt * 0.75 * speed;
    rings.rotation.y = 0.18 * Math.sin(t * 0.4);
    for (let i = 0; i < SPARKS; i++) {
      sparkPos[i * 3 + 1] += sparkSpeed[i] * dt * speed;
      if (sparkPos[i * 3 + 1] > 2.3) sparkPos[i * 3 + 1] = -2.3;
    }
    sparkGeo.attributes.position.needsUpdate = true;

    let wantYaw = -0.22 + 0.1 * Math.sin(t * 0.37) + 0.04 * Math.sin(t * 1.13);
    let wantPitch = 0.03 * Math.sin(t * 0.52), wantRoll = 0.05 * Math.sin(t * 0.29), wantSink = 0;
    if (talking) { wantPitch += 0.035 * Math.sin(t * 8.5); wantRoll += 0.03 * Math.sin(t * 4.1); }
    if (thinking) { wantPitch -= 0.13; wantRoll += 0.14; }
    if (bossState === "fight") { wantYaw = -0.34 + 0.05 * Math.sin(t * 1.4); wantPitch += 0.06; }
    if (bossState === "lost") { wantPitch += 0.34; wantRoll -= 0.1; wantSink = 0.14; }
    yaw = ease(yaw, wantYaw, 5, dt); pitch = ease(pitch, wantPitch, 7, dt); roll = ease(roll, wantRoll, 5, dt); sink = ease(sink, wantSink, 5, dt);
    head.rotation.set(pitch, yaw, roll);
    body.rotation.y = yaw * 0.28;
    body.scale.y = 1 + 0.012 * Math.sin(t * 1.7);

    const since = t - celebrateFrom;
    let hop = bossState === "won" ? Math.abs(Math.sin(t * 5)) * 0.08 : 0, spin = 0;
    if (since < 1.3) { const k = since / 1.3; spin = Math.PI * 2 * k * k * (3 - 2 * k); hop = Math.sin(Math.PI * k) * 0.42; }
    root.rotation.y = spin;
    root.position.y = 0.05 * Math.sin(t * 1.05) - sink + hop;

    const yawSpeed = (yaw - lastYaw) / Math.max(dt, 0.001); lastYaw = yaw;
    for (const s of swaying) {
      s.group.rotation.z = s.swing * Math.sin(t * 0.95 + s.phase) * speed * 1.4 + yawSpeed * 0.06;
      s.group.rotation.x = s.swing * 0.5 * Math.sin(t * 0.7 + s.phase);
    }
    ahoge.rotation.z += 0.14 * Math.sin(t * 3.1) + (talking ? 0.2 * Math.sin(t * 13) : 0);

    if (t > nextBlink) { blinkEnd = t + 0.13; nextBlink = t + 2.4 + Math.random() * 3.6; }
    if (t > nextGaze) {
      gazeX = -14 + Math.random() * 20; gazeY = (Math.random() - 0.5) * 12;
      nextGaze = t + 0.8 + Math.random() * 2.6;
    }
    const happy = HAPPY.test(mood);
    const speech = talking ? Math.round((0.5 + 0.5 * Math.sin(t * 15) * Math.sin(t * 6.3 + 1)) * 4) / 4 : 0;
    const f = { eyes: "open", open: 1, lookX: Math.round(gazeX), lookY: Math.round(gazeY), brow: "", mouth: happy ? "grin" : "smile", open_mouth: speech };
    if (thinking) { f.lookY = -18; f.lookX = 10; f.mouth = "flat"; }
    if (bossState === "fight") { f.brow = "angry"; f.open = 0.86; f.mouth = "flat"; }
    if (bossState === "won") { f.eyes = "star"; f.mouth = "grin"; }
    if (bossState === "lost") { f.eyes = "x"; f.brow = "sad"; f.mouth = "sad"; }
    if (t < blinkEnd && f.eyes === "open") f.eyes = "shut";
    const faceKey = JSON.stringify(f);
    if (faceKey !== shownFace) { shownFace = faceKey; drawFace(f); }

    if (t > nextGlitch) { glitchEnd = t + 0.32; nextGlitch = t + 15 + Math.random() * 25; }
    if (t < glitchEnd) {
      canvas.style.filter = "drop-shadow(-5px 0 #ff2bd6) drop-shadow(5px 0 #20f0ff)";
      canvas.style.transform = `translateX(${(Math.random() - 0.5) * 10}px)`;
    } else if (canvas.style.transform) {
      canvas.style.filter = canvas.style.transform = "";
    }
    if (opts.bubble) opts.bubble.style.opacity = thinking ? 1 : 0;
    renderer.render(scene, camera);
    window.__avatarReady = true;
  }
  canvas.addEventListener("webglcontextlost", e => { e.preventDefault(); setTimeout(() => location.reload(), 3000); });
  requestAnimationFrame(frame);
}
