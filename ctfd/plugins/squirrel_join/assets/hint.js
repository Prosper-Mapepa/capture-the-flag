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
})();
