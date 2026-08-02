// ============================================================
// CONFIG
// ============================================================

const GITHUB_OWNER = "ronenz90";
const GITHUB_REPO = "Cinema_find";

// Fill this in after deploying the Cloudflare Worker (see README) - e.g.
// "https://cinema-find-api.yoursubdomain.workers.dev"
const WORKER_URL = "REPLACE_WITH_YOUR_WORKER_URL";

// SHA-256 hash of the site password. This is only used for the *client-side*
// gate (immediate UI feedback / hiding the form from casual visitors). The
// real check happens server-side in the Worker on every add/edit/delete, so
// this being visible in source doesn't grant write access on its own.
const PASSWORD_HASH_SHA256 = "071dc4f6efd2db563e4daa5d444ac4ba803095191af2ad51a01b3dca1f4fbde2";

const CINEMAS = [
  "סינמה סיטי גלילות",
  'סינמה סיטי ראשל"צ',
  "סינמה סיטי ירושלים",
  "סינמה סיטי כפר-סבא",
  "סינמה סיטי נתניה",
  "סינמה סיטי באר שבע",
  "סינמה סיטי חדרה",
  "סינמה סיטי אשדוד",
];

// ============================================================
// Password gate
// ============================================================

async function sha256Hex(text) {
  const data = new TextEncoder().encode(text);
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(hashBuffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

// The entered password is kept only in sessionStorage (this tab, this
// session) so it can be sent to the Worker on each add/edit/delete call -
// the Worker re-verifies it server-side every time.
function getSessionPassword() {
  return sessionStorage.getItem("cw_password") || "";
}

function unlock() {
  document.getElementById("gate").classList.add("hidden");
  document.getElementById("app").classList.remove("hidden");
  loadMoviesIntoDatalist();
  loadOpenWatches();
}

const gateForm = document.getElementById("gate-form");
const gateError = document.getElementById("gate-error");

gateForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const entered = document.getElementById("password").value;
  const hash = await sha256Hex(entered);
  if (hash === PASSWORD_HASH_SHA256) {
    sessionStorage.setItem("cw_password", entered);
    unlock();
  } else {
    gateError.classList.remove("hidden");
  }
});

if (getSessionPassword()) {
  unlock();
}

// ============================================================
// Tabs
// ============================================================

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.add("hidden"));
    btn.classList.add("active");
    document.getElementById(btn.dataset.tab).classList.remove("hidden");
    if (btn.dataset.tab === "tab-open") loadOpenWatches();
  });
});

// ============================================================
// Populate selects
// ============================================================

const cinemaSelect = document.getElementById("cinema");
CINEMAS.forEach((name) => {
  const opt = document.createElement("option");
  opt.value = name;
  opt.textContent = name;
  cinemaSelect.appendChild(opt);
});

for (const sel of [document.getElementById("hour_from"), document.getElementById("hour_to")]) {
  for (let h = 0; h < 24; h++) {
    const opt = document.createElement("option");
    opt.value = String(h).padStart(2, "0");
    opt.textContent = String(h).padStart(2, "0") + ":00";
    sel.appendChild(opt);
  }
}
document.getElementById("hour_from").value = "00";
document.getElementById("hour_to").value = "23";

// ============================================================
// Movie autocomplete (custom, not native <datalist> - unreliable on mobile)
// ============================================================

let ALL_MOVIES = [];

async function loadMoviesIntoDatalist() {
  try {
    const res = await fetch(`movies.json?_=${Date.now()}`);
    if (!res.ok) {
      console.warn("movies.json fetch returned", res.status);
      return;
    }
    ALL_MOVIES = await res.json();
    console.log(`Loaded ${ALL_MOVIES.length} movie titles for autocomplete.`);
  } catch (e) {
    console.warn("Could not load movies.json (list refreshes nightly):", e);
  }
}

const movieInput = document.getElementById("movie");
const suggestionsBox = document.getElementById("movie-suggestions");

function renderSuggestions(matches) {
  if (!movieInput || !suggestionsBox) return;
  suggestionsBox.innerHTML = "";
  if (!matches.length) {
    suggestionsBox.classList.add("hidden");
    return;
  }
  matches.slice(0, 8).forEach((title) => {
    const item = document.createElement("div");
    item.className = "suggestion-item";
    item.textContent = title;
    item.addEventListener("mousedown", (e) => {
      e.preventDefault();
      movieInput.value = title;
      suggestionsBox.classList.add("hidden");
    });
    suggestionsBox.appendChild(item);
  });
  suggestionsBox.classList.remove("hidden");
}

if (movieInput && suggestionsBox) {
  movieInput.addEventListener("input", () => {
    const query = movieInput.value.trim();
    if (!query || !ALL_MOVIES.length) {
      suggestionsBox.classList.add("hidden");
      return;
    }
    renderSuggestions(ALL_MOVIES.filter((title) => title.includes(query)));
  });
  movieInput.addEventListener("focus", () => {
    if (movieInput.value.trim() && ALL_MOVIES.length) {
      renderSuggestions(ALL_MOVIES.filter((title) => title.includes(movieInput.value.trim())));
    }
  });
  movieInput.addEventListener("blur", () => {
    setTimeout(() => suggestionsBox.classList.add("hidden"), 100);
  });
} else {
  console.warn("Movie autocomplete elements not found - is index.html up to date?");
}

// ============================================================
// Calling the Worker API
// ============================================================

async function callWorker(action, fields) {
  const res = await fetch(WORKER_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password: getSessionPassword(), action, ...fields }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || `Request failed (${res.status})`);
  }
  return data;
}

function showStatus(elementId, message, isError) {
  const el = document.getElementById(elementId);
  if (!el) return;
  el.textContent = message;
  el.classList.remove("hidden");
  el.classList.toggle("error", !!isError);
  el.classList.toggle("success", !isError);
}

// ============================================================
// Add watch form
// ============================================================

document.getElementById("watch-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const submitBtn = e.target.querySelector("button[type=submit]");
  submitBtn.disabled = true;

  const fields = {
    cinema: document.getElementById("cinema").value,
    hall_type: document.getElementById("hall_type").value,
    movie: document.getElementById("movie").value.trim(),
    hour_from: document.getElementById("hour_from").value,
    hour_to: document.getElementById("hour_to").value,
    email: document.getElementById("email").value.trim(),
  };

  try {
    const result = await callWorker("add", fields);
    if (result.skipped) {
      showStatus("add-status", "המעקב הזה כבר קיים.", false);
    } else {
      showStatus("add-status", "המעקב נוסף בהצלחה!", false);
      document.getElementById("watch-form").reset();
      document.getElementById("hour_from").value = "00";
      document.getElementById("hour_to").value = "23";
    }
  } catch (err) {
    showStatus("add-status", `שגיאה: ${err.message}`, true);
  } finally {
    submitBtn.disabled = false;
  }
});

// ============================================================
// Open watches tab: list / edit / delete
// ============================================================

async function loadOpenWatches() {
  const container = document.getElementById("watches-list");
  container.textContent = "טוען...";
  try {
    const res = await fetch(WORKER_URL, { method: "GET" });
    const watches = await res.json();
    if (!res.ok) throw new Error(watches.error || `Request failed (${res.status})`);
    if (!watches.length) {
      container.textContent = "אין כרגע מעקבים פעילים.";
      return;
    }
    container.innerHTML = "";
    watches.forEach((w) => container.appendChild(renderWatchRow(w)));
  } catch (e) {
    container.textContent = "שגיאה בטעינת המעקבים.";
    console.error(e);
  }
}

function renderWatchRow(watch) {
  const row = document.createElement("div");
  row.className = "watch-row";

  const info = document.createElement("div");
  info.className = "watch-info";
  info.innerHTML = `
    <strong>${watch.movie}</strong><br/>
    ${watch.cinema} · ${watch.hall_type}<br/>
    שעות: ${watch.hour_from || "00"}:00–${watch.hour_to || "23"}:00
    ${watch.email ? `<br/>מייל: ${watch.email}` : ""}
  `;

  const actions = document.createElement("div");
  actions.className = "watch-actions";

  const editBtn = document.createElement("button");
  editBtn.textContent = "ערוך";
  editBtn.className = "secondary";
  editBtn.addEventListener("click", () => handleEdit(watch));

  const delBtn = document.createElement("button");
  delBtn.textContent = "מחק";
  delBtn.className = "danger";
  delBtn.addEventListener("click", () => handleDelete(watch));

  actions.appendChild(editBtn);
  actions.appendChild(delBtn);
  row.appendChild(info);
  row.appendChild(actions);
  return row;
}

async function handleEdit(watch) {
  const hourFrom = prompt("שעה התחלה (0-23):", watch.hour_from || "00");
  if (hourFrom === null) return;
  const hourTo = prompt("שעה סיום (0-23):", watch.hour_to || "23");
  if (hourTo === null) return;
  const email = prompt("מייל ליעד ההתראה (ריק = ברירת מחדל):", watch.email || "");
  if (email === null) return;

  try {
    await callWorker("edit", {
      id: watch.id,
      hour_from: hourFrom.padStart(2, "0"),
      hour_to: hourTo.padStart(2, "0"),
      email: email.trim(),
    });
    loadOpenWatches();
  } catch (err) {
    alert(`שגיאה בעדכון: ${err.message}`);
  }
}

async function handleDelete(watch) {
  if (!confirm(`למחוק את המעקב עבור "${watch.movie}"?`)) return;
  try {
    await callWorker("delete", { id: watch.id });
    loadOpenWatches();
  } catch (err) {
    alert(`שגיאה במחיקה: ${err.message}`);
  }
}
