(function () {
  function ask(cost) {
    return new Promise(function (resolve) {
      const wrap = document.createElement("div");
      wrap.className = "hint-ask";
      wrap.innerHTML =
        '<div class="hint-ask-card" role="dialog" aria-modal="true" aria-labelledby="hint-ask-title">' +
        '<h2 id="hint-ask-title">Unlock this hint?</h2>' +
        "<p></p>" +
        '<div class="hint-ask-actions">' +
        '<button type="button" class="hint-no">Not now</button>' +
        '<button type="button" class="hint-yes">Unlock</button>' +
        "</div></div>";
      const points = Number(cost);
      wrap.querySelector("p").textContent =
        points > 0
          ? "It costs " + points + " points. Your whole team shares that score."
          : "Your whole team will see this hint.";
      function done(answer) {
        wrap.remove();
        resolve(answer);
      }
      wrap.querySelector(".hint-no").addEventListener("click", function () {
        done(false);
      });
      wrap.querySelector(".hint-yes").addEventListener("click", function () {
        done(true);
      });
      wrap.addEventListener("click", function (event) {
        if (event.target === wrap) done(false);
      });
      document.body.appendChild(wrap);
      wrap.querySelector(".hint-yes").focus();
    });
  }

  function install() {
    if (!window.CTFd || !CTFd._functions || !CTFd._functions.challenge) return false;
    if (CTFd._functions.challenge.displayUnlock && CTFd._functions.challenge.displayUnlock.squirrel) {
      return true;
    }
    function friendlyUnlock() {
      const open = document.querySelector("#challenge-window details[open]");
      return ask(open ? open.getAttribute("data-cost") : 0);
    }
    friendlyUnlock.squirrel = true;
    CTFd._functions.challenge.displayUnlock = friendlyUnlock;
    return true;
  }

  const timer = setInterval(function () {
    if (install()) clearInterval(timer);
  }, 100);
  setTimeout(function () {
    clearInterval(timer);
  }, 10000);

  function inQuestion(event) {
    const desc = document.querySelector("#challenge-window .challenge-desc");
    if (!desc) return false;
    const path = event.composedPath ? event.composedPath() : [];
    return path.indexOf(desc) !== -1;
  }

  ["copy", "cut", "dragstart", "contextmenu"].forEach(function (name) {
    document.addEventListener(
      name,
      function (event) {
        if (inQuestion(event)) event.preventDefault();
      },
      true
    );
  });

  function openChallenge(name) {
    const buttons = document.querySelectorAll(".challenge-button");
    for (let i = 0; i < buttons.length; i += 1) {
      const label = buttons[i].querySelector("p");
      if (label && label.textContent.trim() === name) {
        buttons[i].click();
        return;
      }
    }
  }

  function fillStep(modal) {
    if (!modal || modal.dataset.ready === "1" || modal.classList.contains("step-live")) return;
    modal.dataset.ready = "1";
    const nameNode = document.querySelector("#challenge-window .challenge-name");
    const building = document.querySelector("#challenge-window .building-link");
    const dialog = modal.cloneNode(true);
    const title = dialog.querySelector(".step-title");
    const body = dialog.querySelector(".step-body");
    const go = dialog.querySelector(".step-go");
    const stay = dialog.querySelector(".step-stay");
    if (!title || !body || !go || !stay) return;
    dialog.dataset.ready = "1";
    dialog.classList.add("step-live");
    modal.hidden = true;
    const challenge = nameNode ? nameNode.textContent.trim() : "";
    if (challenge === "Squirrel Door Note") {
      title.textContent = "Door flag accepted";
      body.textContent = "Next, open Snack Closet Log. Decode the log before you walk inside.";
      go.textContent = "Go to the closet puzzle";
      go.addEventListener("click", function (event) {
        event.preventDefault();
        dialog.remove();
        openChallenge("Snack Closet Log");
      });
    } else {
      title.textContent = "Closet flag accepted";
      body.textContent = "Next, open the building and type the code on the keypad so the squirrels hop free.";
      go.textContent = "Go to the building";
      if (building) {
        go.href = building.href;
        go.target = "_blank";
        go.rel = "opener";
      }
    }
    stay.addEventListener("click", function () {
      dialog.remove();
    });
    const previous = document.querySelector("body > .step-modal.step-live");
    if (previous) previous.remove();
    document.body.appendChild(dialog);
    go.focus();
  }

  function rememberUnlock(raw) {
    String(raw || "")
      .split(",")
      .forEach(function (step) {
        if (step === "door" || step === "closet") {
          sessionStorage.setItem("squirrel-unlock-" + step, "1");
        }
      });
  }

  const hashUnlock = new URLSearchParams(location.hash.replace(/^#/, "")).get("unlock");
  if (hashUnlock) rememberUnlock(hashUnlock);

  window.addEventListener("message", function (event) {
    const data = event.data;
    if (!data || data.source !== "squirrel-rescue") return;
    rememberUnlock(data.step);
    applyFlagGate();
  });

  function applyFlagGate() {
    const nameNode = document.querySelector("#challenge-window .challenge-name");
    const input = document.querySelector("#challenge-input");
    const submit = document.querySelector("#challenge-submit");
    const gate = document.querySelector("#flag-gate");
    if (!nameNode || !input || !submit || !gate) return;
    const name = nameNode.textContent.trim();
    const step = name === "Snack Closet Log" ? "closet" : name === "Squirrel Door Note" ? "door" : "";
    if (!step) return;
    const open = sessionStorage.getItem("squirrel-unlock-" + step) === "1";
    const locked = !open;
    const placeholder = open ? "Paste the flag" : "Flag box is closed";
    const message = step === "closet"
      ? "This box stays closed until the snack keypad accepts the code."
      : "This box stays closed until the building accepts the door PIN.";
    if (input.disabled !== locked) input.disabled = locked;
    if (submit.disabled !== locked) submit.disabled = locked;
    if (input.placeholder !== placeholder) input.placeholder = placeholder;
    if (gate.hidden !== open) gate.hidden = open;
    if (gate.textContent !== message) gate.textContent = message;
  }

  function watchChallenge() {
    const root = document.getElementById("challenge-window");
    if (!root || root.dataset.watched === "1") return;
    root.dataset.watched = "1";
    let painting = false;
    const watcher = new MutationObserver(function () {
      if (painting) return;
      painting = true;
      watcher.disconnect();
      try {
        const modals = root.querySelectorAll(".step-modal");
        for (let i = 0; i < modals.length; i += 1) fillStep(modals[i]);
        applyFlagGate();
        stampTeamLinks();
      } finally {
        painting = false;
        watcher.observe(root, { childList: true, subtree: true });
      }
    });
    watcher.observe(root, { childList: true, subtree: true });
  }

  function stampTeamLinks() {
    const team = window.init && window.init.teamName;
    const side = team === "Red" ? "red" : team === "Blue" ? "blue" : "";
    if (!side) return;
    let buildingUrl = null;
    document.querySelectorAll("a[href]").forEach(function (link) {
      if (link.textContent.trim() !== "The building") return;
      try {
        buildingUrl = new URL(link.href);
      } catch (error) {
        buildingUrl = null;
      }
    });
    document.querySelectorAll("a[href]").forEach(function (link) {
      let url;
      try {
        url = new URL(link.href, location.href);
      } catch (error) {
        return;
      }
      const sameBuilding = buildingUrl && url.origin === buildingUrl.origin && url.pathname.replace(/\/$/, "") === buildingUrl.pathname.replace(/\/$/, "");
      if (!sameBuilding && !link.classList.contains("building-link")) return;
      if (url.searchParams.get("side") === side) return;
      url.searchParams.set("side", side);
      link.href = url.toString();
    });
  }

  stampTeamLinks();
  watchChallenge();
})();
