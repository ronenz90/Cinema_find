// ============================================================
// CONFIG
// ============================================================

const GITHUB_OWNER = "ronenz90";
const GITHUB_REPO = "Cinema_find";

// SHA-256 hash of the site password (not the password itself).
// Only keeps casual visitors out - see README for why this isn't "real" security.
const PASSWORD_HASH_SHA256 = "071dc4f6efd2db563e4daa5d444ac4ba803095191af2ad51a01b3dca1f4fbde2";

// Base cinema names (hall type is chosen separately below).
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

const RAW_BASE = `https://raw.githubusercontent.com/${GITHUB_OWNER}/${GITHUB_REPO}/main`;

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

const gateForm = document.getElementById("gate-form");
const gateError = document.getElementById("gate-error");

function unlock() {
  document.getElementById("gate").classList.add("hidden");
  document.getElementById("app").classList.remove("hidden");
  loadMoviesIntoDatalist();
  loadOpenWatches();
}

gateForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const entered = document.getElementById("password").value;
  const hash = await sha256Hex(entered);
  if (hash === PASSWORD_HASH_SHA256) {
    sessionStorage.setItem("cw_unlocked", "1");
    unlock();
  } else {
    gateError.classList.remove("hidden");
  }
});

if (sessionStorage.getItem("cw_unlocked") === "1") {
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
// Populate selects / datalist
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
    const label = String(h).padStart(2, "0") + ":00";
    opt.value = String(h).padStart(2, "0");
    opt.textContent = label;
    sel.appendChild(opt);
  }
}
document.getElementById("hour_from").value = "00";
document.getElementById("hour_to").value = "23";

let ALL_MOVIES = [];

async function loadMoviesIntoDatalist() {
  try {
    const res = await fetch(`movies.json?_=${Date.now()}`);
    if (!res.ok) return;
    ALL_MOVIES = await res.json();
  } catch (e) {
    console.warn("Could not load movies.json (list refreshes nightly):", e);
  }
}

const movieInput = document.getElementById("movie");
const suggestionsBox = document.getElementById("movie-suggestions");

function renderSuggestions(matches) {
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
      // mousedown (not click) fires before the input's blur event hides the box
      e.preventDefault();
      movieInput.value = title;
      suggestionsBox.classList.add("hidden");
    });
    suggestionsBox.appendChild(item);
  });
  suggestionsBox.classList.remove("hidden");
}

movieInput.addEventListener("input", () => {
  const query = movieInput.value.trim();
  if (!query || !ALL_MOVIES.length) {
    suggestionsBox.classList.add("hidden");
    return;
  }
  const matches = ALL_MOVIES.filter((title) => title.includes(query));
  renderSuggestions(matches);
});

movieInput.addEventListener("focus", () => {
  if (movieInput.value.trim() && ALL_MOVIES.length) {
    const matches = ALL_MOVIES.filter((title) => title.includes(movieInput.value.trim()));
    renderSuggestions(matches);
  }
});

movieInput.addEventListener("blur", () => {
  // slight delay so a suggestion's mousedown can still register first
  setTimeout(() => suggestionsBox.classList.add("hidden"), 100);
});

// ============================================================
// Helpers to open a pre-filled GitHub issue
// ============================================================

function openIssue(label, title, bodyLines) {
  const body = bodyLines.join("\n");
  const url =
    `https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/issues/new` +
    `?labels=${encodeURIComponent(label)}` +
    `&title=${encodeURIComponent(title)}` +
    `&body=${encodeURIComponent(body)}`;
  window.open(url, "_blank", "noopener");
}

// ============================================================
// Add watch form
// ============================================================

document.getElementById("watch-form").addEventListener("submit", (e) => {
  e.preventDefault();

  const cinema = document.getElementById("cinema").value;
  const hallType = document.getElementById("hall_type").value;
  const movie = document.getElementById("movie").value.trim();
  const hourFrom = document.getElementById("hour_from").value;
  const hourTo = document.getElementById("hour_to").value;
  const email = document.getElementById("email").value.trim();

  const bodyLines = [
    `cinema: ${cinema}`,
    `hall_type: ${hallType}`,
    `movie: ${movie}`,
    `hour_from: ${hourFrom}`,
    `hour_to: ${hourTo}`,
  ];
  if (email) bodyLines.push(`email: ${email}`);

  openIssue("watch-request", `Watch request: ${movie} @ ${cinema} (${hallType})`, bodyLines);
});

// ============================================================
// Open watches tab: list / edit / delete
// ============================================================

async function loadOpenWatches() {
  const container = document.getElementById("watches-list");
  container.textContent = "טוען...";
  try {
    const res = await fetch(`${RAW_BASE}/config/watches.json?_=${Date.now()}`);
    const watches = await res.json();
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
  editBtn.addEventListener("click", () => openEditForm(watch));

  const delBtn = document.createElement("button");
  delBtn.textContent = "מחק";
  delBtn.className = "danger";
  delBtn.addEventListener("click", () => {
    if (!confirm(`למחוק את המעקב עבור "${watch.movie}"?`)) return;
    openIssue("watch-delete", `Delete watch: ${watch.movie} @ ${watch.cinema}`, [`id: ${watch.id}`]);
  });

  actions.appendChild(editBtn);
  actions.appendChild(delBtn);
  row.appendChild(info);
  row.appendChild(actions);
  return row;
}

function openEditForm(watch) {
  const hourFrom = prompt("שעה התחלה (0-23):", watch.hour_from || "00");
  if (hourFrom === null) return;
  const hourTo = prompt("שעה סיום (0-23):", watch.hour_to || "23");
  if (hourTo === null) return;
  const email = prompt("מייל ליעד ההתראה (ריק = ברירת מחדל):", watch.email || "");
  if (email === null) return;

  const bodyLines = [`id: ${watch.id}`, `hour_from: ${hourFrom.padStart(2, "0")}`, `hour_to: ${hourTo.padStart(2, "0")}`];
  bodyLines.push(`email: ${email.trim()}`);

  openIssue("watch-edit", `Edit watch: ${watch.movie} @ ${watch.cinema}`, bodyLines);
}
