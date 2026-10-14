const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const stage = document.getElementById("stage");
const walker = document.getElementById("walker");
const roomActor = document.getElementById("room-actor");
const pen = document.getElementById("pen");
const building = document.getElementById("building");
const prop = document.getElementById("prop");
const propScreen = document.getElementById("prop-screen");
const propLed = document.getElementById("prop-led");
const doorLed = document.getElementById("door-led");
const intercom = document.getElementById("intercom-screen");
const endcard = document.getElementById("endcard");
const feedback = document.getElementById("feedback");
const enterBtn = document.getElementById("enter-btn");
const resetBtn = document.getElementById("reset-btn");
const clock = document.getElementById("clock");
const triesEl = document.getElementById("tries");
const slotsEl = document.getElementById("slots");
const keysEl = document.getElementById("keys");
const flagList = document.getElementById("flag-list");
const boardLink = document.getElementById("board-link");

let cfg = { scoreboard: "http://localhost:8000", door_digits: 6, disarm_digits: 6, tries: 3, seconds: 300 };
let scene = "approach";
let token = null;
let lastDoor = "";
let typed = "";
let secondsLeft = 0;
let timerHandle = null;
let busy = false;
let audioCtx = null;
let muted = false;
let flags = [];

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, reduce ? 0 : ms));

function setText(id, value) {
  document.getElementById(id).textContent = value;
}

function setPen(state) {
  pen.classList.remove("locked", "free", "flinch");
  pen.classList.add(state);
}

function setScene(next) {
  scene = next;
  stage.classList.remove("scene-street", "scene-closet", "scene-safe", "scene-boom", "deny");
  if (next === "closet") stage.classList.add("scene-closet");
  else if (next === "safe") stage.classList.add("scene-safe");
  else if (next === "boom") stage.classList.add("scene-boom");
  else stage.classList.add("scene-street");

  const outside = next === "approach" || next === "door" || next === "held";
  document.getElementById("beat-door").classList.toggle("on", outside);
  document.getElementById("beat-in").classList.toggle("on", next === "closet");
  document.getElementById("beat-end").classList.toggle("on", next === "safe" || next === "boom");

  const copy = {
    approach: ["Outside", "Acorn Hall door", "A rescue runner is heading for Acorn Hall. The Chippewa squirrels are locked inside. The PIN is in the Squirrel Door Note challenge."],
    door: ["Outside", "Door intercom", "Type the door PIN from the clipboard. A wrong PIN keeps the squirrels inside and you outside."],
    held: ["Door open", "Lobby", "Copy the door flag. Decode the Snack Closet Log before you walk in. The snack timer starts when you enter the closet."],
    closet: ["Snack closet", "Squirrel keypad", "Type the digits from the groundskeeper log. A full wrong code spends a try. Three wrong codes, or the timer, sends the squirrels scattering."],
    boom: ["Rescue failed", "Squirrels scattered", "The acorn alarm went off. Your door flag still counts. Restart and use the code from the log."],
    safe: ["Rescue complete", "Squirrels freed", "The closet popped open. Copy this flag to the scoreboard."],
  };
  const [eye, title, body] = copy[next];
  setText("eyebrow", eye);
  setText("panel-title", title);
  setText("panel-copy", body);
  keysEl.hidden = next === "approach" || next === "held" || next === "boom" || next === "safe";
  slotsEl.hidden = keysEl.hidden;
  enterBtn.hidden = next !== "held";
  resetBtn.hidden = next !== "boom" && next !== "safe";
  clock.hidden = next !== "closet" && next !== "safe";
  triesEl.hidden = next !== "closet";
  renderSlots();
  renderFlags();
  if (next === "safe") showCelebration();
  else if (next === "boom") showAlarm();
  else clearFinale();
}

function renderSlots() {
  const size = scene === "closet" ? cfg.disarm_digits : cfg.door_digits;
  slotsEl.replaceChildren();
  for (let i = 0; i < size; i += 1) {
    const box = document.createElement("span");
    box.textContent = typed[i] || "";
    slotsEl.appendChild(box);
  }
  if (scene === "closet") {
    propScreen.textContent = formatClock(secondsLeft);
  }
  intercom.textContent = scene === "held" || scene === "safe" ? "OPEN" : (typed || "READY");
}

function formatClock(total) {
  const mins = String(Math.floor(total / 60)).padStart(2, "0");
  const secs = String(total % 60).padStart(2, "0");
  return `${mins}:${secs}`;
}

function setFeedback(message, kind) {
  feedback.textContent = message || "";
  feedback.className = "feedback" + (kind ? " " + kind : "");
}

function notifyScoreboard(label) {
  const step = label === "Door flag" ? "door" : "closet";
  const message = { source: "squirrel-rescue", step };
  if (window.opener && !window.opener.closed) {
    window.opener.postMessage(message, "*");
  }
  const steps = [];
  if (flags.some((row) => row.label === "Door flag")) steps.push("door");
  if (flags.some((row) => row.label === "Rescue flag")) steps.push("closet");
  const url = new URL(cfg.scoreboard, window.location.href);
  if (steps.length) url.hash = "unlock=" + steps.join(",");
  boardLink.href = url.toString();
}

function addFlag(label, value) {
  if (!value || flags.some((row) => row.value === value)) {
    renderFlags();
    notifyScoreboard(label);
    return;
  }
  flags.push({ label, value });
  renderFlags();
  notifyScoreboard(label);
}

function renderFlags() {
  const inside = scene === "closet" || scene === "safe" || scene === "boom";
  const shown = flags.filter((row) => (inside ? row.label !== "Door flag" : row.label === "Door flag"));
  flagList.replaceChildren();
  flagList.hidden = shown.length === 0;
  shown.forEach((row) => {
    const card = document.createElement("div");
    card.className = "flag-card";
    const name = document.createElement("p");
    name.textContent = row.label;
    const code = document.createElement("code");
    code.textContent = row.value;
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "Copy flag";
    button.addEventListener("click", async () => {
      notifyScoreboard(row.label);
      try {
        await navigator.clipboard.writeText(row.value);
        button.textContent = "Copied";
      } catch (_err) {
        button.textContent = "Select the flag and copy it";
      }
    });
    card.append(name, code, button);
    flagList.appendChild(card);
  });
}

function typeDigit(digit) {
  const size = scene === "closet" ? cfg.disarm_digits : cfg.door_digits;
  if (scene !== "door" && scene !== "closet") return;
  if (typed.length >= size) return;
  typed += digit;
  renderSlots();
  blip(520, 0.04, "square", 0.02);
}

function backspace() {
  typed = typed.slice(0, -1);
  renderSlots();
}

function clearTyped() {
  typed = "";
  renderSlots();
}

async function post(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  data.status = response.status;
  return data;
}

async function submitCurrent() {
  if (busy) return;
  try {
    if (scene === "door") await submitDoor(typed);
    else if (scene === "closet") await submitDisarm(typed);
  } catch (_err) {
    busy = false;
    setFeedback("The simulator could not reach the server.", "bad");
  }
}

async function submitDoor(code, auto) {
  busy = true;
  setFeedback("Checking the door…");
  const data = await post("/api/door", { code });
  busy = false;
  if (!data.ok) {
    if (!auto) {
      stage.classList.add("deny");
      doorLed.className = "led bad";
      intercom.textContent = "NO";
      setFeedback(data.message, "bad");
      blip(140, 0.25, "sawtooth", 0.03);
      await wait(700);
      stage.classList.remove("deny");
      doorLed.className = "led";
      renderSlots();
    }
    return false;
  }
  token = data.token;
  lastDoor = code;
  typed = "";
  walker.classList.remove("walk", "through");
  walker.classList.add("at-door");
  doorLed.className = "led ok";
  intercom.textContent = "OPEN";
  building.classList.add("open");
  addFlag("Door flag", data.flag);
  setFeedback(data.message, "good");
  blip(660, 0.08, "sine", 0.03);
  setScene("held");
  return true;
}

async function walkInside() {
  if (scene !== "held" || !token) return;
  enterBtn.disabled = true;
  walker.classList.remove("at-door");
  walker.classList.add("through");
  await wait(1450);
  walker.classList.remove("through");
  secondsLeft = cfg.seconds;
  setFeedback("");
  setScene("closet");
  setPen("locked");
  roomActor.classList.add("idle");
  triesEl.textContent = `Tries left: ${cfg.tries}`;
  clock.classList.remove("safe");
  prop.classList.remove("safe", "jolt");
  propLed.className = "led bad";
  propScreen.textContent = formatClock(secondsLeft);
  clock.textContent = formatClock(secondsLeft);
  clock.hidden = false;
  clearTyped();
  startTimer();
  enterBtn.disabled = false;
}

function startTimer() {
  stopTimer();
  timerHandle = setInterval(() => {
    if (scene !== "closet") return;
    secondsLeft -= 1;
    const label = formatClock(Math.max(secondsLeft, 0));
    propScreen.textContent = label;
    clock.textContent = label;
    const pitch = secondsLeft <= 30 ? 980 : 720;
    blip(pitch, 0.03, "square", 0.015);
    if (secondsLeft <= 0) {
      stopTimer();
      expire();
    }
  }, reduce ? 50 : 1000);
}

function stopTimer() {
  if (timerHandle) clearInterval(timerHandle);
  timerHandle = null;
}

async function submitDisarm(code) {
  busy = true;
  const data = await post("/api/disarm", { code, token });
  busy = false;
  if (data.status === 403) {
    stopTimer();
    setFeedback(data.message, "bad");
    returnToDoor();
    return;
  }
  if (data.ok) {
    succeed(data.flag, data.message);
    return;
  }
  if (data.exploded) {
    failRun(data.message);
    return;
  }
  if (data.counted === false) {
    setFeedback(data.message, "bad");
    return;
  }
  prop.classList.remove("jolt");
  void prop.offsetWidth;
  prop.classList.add("jolt");
  pen.classList.remove("flinch");
  void pen.offsetWidth;
  pen.classList.add("flinch");
  triesEl.textContent = `Tries left: ${data.attempts_left}`;
  setFeedback(data.message, "bad");
  blip(110, 0.22, "sawtooth", 0.04);
  clearTyped();
}

async function expire() {
  const data = await post("/api/timeout", { token });
  failRun(data.message || "Time's up. The acorn alarm sent the squirrels scattering.");
}

function succeed(flag, message) {
  stopTimer();
  prop.classList.add("safe");
  propLed.className = "led ok";
  propScreen.textContent = "SAFE";
  clock.textContent = "SAFE";
  clock.classList.add("safe");
  roomActor.classList.remove("idle");
  roomActor.classList.add("cheer");
  setPen("free");
  addFlag("Rescue flag", flag);
  setFeedback(message, "good");
  showEnd("Squirrels freed", "The snack closet popped open and the Chippewa squirrels hopped out.", "good");
  setScene("safe");
  chord();
}

function failRun(message) {
  stopTimer();
  spawnDebris();
  showEnd("Squirrels scattered", message, "bad");
  setScene("boom");
  setFeedback(message, "bad");
  boom();
}

function showEnd(title, message, kind) {
  endcard.hidden = false;
  endcard.className = "endcard " + kind;
  setText("end-title", title);
  setText("end-copy", message);
}

function returnToDoor() {
  token = null;
  building.classList.add("open");
  walker.classList.add("at-door");
  endcard.hidden = true;
  setScene("door");
}

async function restart() {
  stopTimer();
  endcard.hidden = true;
  prop.classList.remove("safe", "jolt");
  propLed.className = "led";
  roomActor.classList.remove("cheer");
  roomActor.classList.add("idle");
  setPen("locked");
  document.getElementById("debris").replaceChildren();
  clearTyped();
  if (!lastDoor) {
    building.classList.remove("open");
    walker.classList.add("at-door");
    setScene("door");
    return;
  }
  setFeedback("Using the PIN that already opened Acorn Hall…");
  const ok = await submitDoor(lastDoor, true);
  if (!ok) setScene("door");
}

function clearFinale() {
  const finale = document.getElementById("finale");
  finale.hidden = true;
  finale.className = "finale";
  finale.replaceChildren();
}

function makeSquirrel() {
  const squirrel = document.createElement("div");
  squirrel.className = "squirrel";
  squirrel.innerHTML =
    '<span class="tail"></span><span class="ear l"></span><span class="ear r"></span><span class="head"><i></i></span><span class="body"></span><span class="paw l"></span><span class="paw r"></span>';
  return squirrel;
}

function showCelebration() {
  const finale = document.getElementById("finale");
  finale.hidden = false;
  finale.className = "finale celebrate";
  finale.replaceChildren();
  const colors = ["#ffc82e", "#6a0032", "#1f8a4c", "#fffdf8", "#e04b4b", "#3d7de0"];
  const confetti = document.createElement("div");
  confetti.className = "confetti";
  for (let i = 0; i < 90; i += 1) {
    const bit = document.createElement("i");
    bit.style.left = `${Math.random() * 100}%`;
    bit.style.background = colors[i % colors.length];
    bit.style.animationDelay = `${Math.random() * -3}s`;
    bit.style.animationDuration = `${2.4 + Math.random() * 2.2}s`;
    bit.style.setProperty("--rest", `${6 + Math.random() * 88}%`);
    bit.style.setProperty("--spin", `${Math.random() * 360}deg`);
    confetti.appendChild(bit);
  }
  const herd = document.createElement("div");
  herd.className = "herd";
  for (let i = 0; i < 7; i += 1) {
    const runner = document.createElement("div");
    runner.className = "runner" + (i % 2 ? " flip" : "") + (i % 3 === 0 ? " small" : "");
    runner.style.top = `${6 + (i * 12) % 78}%`;
    runner.style.animationDuration = `${5 + (i % 4)}s`;
    runner.style.animationDelay = `${-i * 0.7}s`;
    runner.style.setProperty("--spot", `${8 + i * 12}%`);
    runner.appendChild(makeSquirrel());
    herd.appendChild(runner);
  }
  finale.append(confetti, herd);
}

function showAlarm() {
  const finale = document.getElementById("finale");
  finale.hidden = false;
  finale.className = "finale alarm";
  finale.replaceChildren();
}

function spawnDebris() {
  const layer = document.getElementById("debris");
  layer.replaceChildren();
  for (let i = 0; i < 16; i += 1) {
    const bit = document.createElement("i");
    bit.style.setProperty("--dx", `${(Math.random() - 0.5) * 280}px`);
    bit.style.setProperty("--dy", `${-40 - Math.random() * 180}px`);
    bit.style.setProperty("--rot", `${Math.random() * 240}deg`);
    bit.style.background = i % 2 ? "#ffb15a" : "#8d97a8";
    layer.appendChild(bit);
  }
}

function blip(freq, dur, type, gainValue) {
  if (muted) return;
  const ctx = context();
  if (!ctx) return;
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = type;
  osc.frequency.value = freq;
  gain.gain.value = gainValue;
  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.start();
  gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + dur);
  osc.stop(ctx.currentTime + dur);
}

function chord() {
  blip(523, 0.12, "sine", 0.03);
  setTimeout(() => blip(659, 0.12, "sine", 0.03), 90);
  setTimeout(() => blip(784, 0.18, "sine", 0.03), 180);
}

function boom() {
  if (muted) return;
  const ctx = context();
  if (!ctx) return;
  const frames = 2 * ctx.sampleRate;
  const buffer = ctx.createBuffer(1, frames, ctx.sampleRate);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < frames; i += 1) data[i] = (Math.random() * 2 - 1) * (1 - i / frames);
  const source = ctx.createBufferSource();
  const gain = ctx.createGain();
  const filter = ctx.createBiquadFilter();
  filter.type = "lowpass";
  filter.frequency.value = 240;
  source.buffer = buffer;
  gain.gain.value = 0.18;
  source.connect(filter);
  filter.connect(gain);
  gain.connect(ctx.destination);
  source.start();
}

function context() {
  const Ctx = window.AudioContext || window.webkitAudioContext;
  if (!Ctx) return null;
  if (!audioCtx) audioCtx = new Ctx();
  if (audioCtx.state === "suspended") audioCtx.resume();
  return audioCtx;
}

function buildKeys() {
  const labels = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "Clear", "0", "Enter"];
  labels.forEach((label) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "key" + (label === "Clear" ? " clear" : label === "Enter" ? " enter" : "");
    button.textContent = label;
    button.addEventListener("click", () => {
      if (label === "Clear") clearTyped();
      else if (label === "Enter") submitCurrent();
      else typeDigit(label);
    });
    keysEl.appendChild(button);
  });
}

document.getElementById("lane-red").addEventListener("click", () => chooseLane("red"));
document.getElementById("lane-blue").addEventListener("click", () => chooseLane("blue"));
document.getElementById("mute").addEventListener("click", () => {
  muted = !muted;
  document.getElementById("mute").textContent = muted ? "Sound off" : "Sound on";
});
enterBtn.addEventListener("click", walkInside);
resetBtn.addEventListener("click", restart);
document.addEventListener("keydown", (event) => {
  if (event.metaKey || event.ctrlKey || event.altKey) return;
  if (event.key >= "0" && event.key <= "9") typeDigit(event.key);
  else if (event.key === "Backspace") backspace();
  else if (event.key === "Escape") clearTyped();
  else if (event.key === "Enter") submitCurrent();
});

function chooseLane(side, locked) {
  if (side !== "red" && side !== "blue") return;
  document.body.dataset.side = side;
  document.body.classList.toggle("lane-locked", Boolean(locked));
  document.getElementById("lane-red").classList.toggle("on", side === "red");
  document.getElementById("lane-blue").classList.toggle("on", side === "blue");
  sessionStorage.setItem("sweep-lane", side);
  if (locked) sessionStorage.setItem("sweep-lane-locked", side);
}

function laneFromJoin() {
  const asked = new URLSearchParams(location.search).get("side");
  if (asked === "red" || asked === "blue") return { side: asked, locked: true };
  const saved = sessionStorage.getItem("sweep-lane");
  const lockedSide = sessionStorage.getItem("sweep-lane-locked");
  if ((saved === "red" || saved === "blue") && lockedSide === saved) return { side: saved, locked: true };
  if (saved === "red" || saved === "blue") return { side: saved, locked: false };
  return null;
}

async function boot() {
  try {
    cfg = await fetch("/api/config").then((response) => response.json());
  } catch (_err) {
    setFeedback("The simulator server is not responding.", "bad");
  }
  boardLink.href = cfg.scoreboard;
  buildKeys();
  renderFlags();
  const joined = laneFromJoin();
  if (joined) chooseLane(joined.side, joined.locked);
  setScene("approach");
  propScreen.textContent = formatClock(cfg.seconds);
  walker.classList.add("walk");
  await wait(3100);
  walker.classList.remove("walk");
  walker.classList.add("at-door");
  setScene("door");
}

boot();
