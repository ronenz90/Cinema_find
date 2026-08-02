/**
 * Cinema Watcher API - Cloudflare Worker
 * =======================================
 * A tiny serverless proxy that lets the public GitHub Pages site add/edit/
 * delete watches instantly, without ever exposing a GitHub write token to
 * the browser and without needing a manual "confirm" click on GitHub.
 *
 * How it works:
 *   1. The browser POSTs { password, action, ...fields } to this Worker.
 *   2. The Worker hashes the password and compares it to PASSWORD_HASH
 *      (a secret set in the Worker's settings, never sent to the browser).
 *   3. If it matches, the Worker reads config/watches.json from the repo
 *      via the GitHub Contents API (using GITHUB_TOKEN, also a Worker
 *      secret), applies the add/edit/delete, and writes it back - all
 *      server-side, in one request/response cycle.
 *
 * Required Worker secrets/vars (set in Cloudflare dashboard, see README):
 *   GITHUB_TOKEN    (secret) - fine-grained PAT, this repo only,
 *                              "Contents: Read and write" permission
 *   PASSWORD_HASH   (secret) - SHA-256 hex hash of the site password
 *   GITHUB_OWNER    (var)    - e.g. "ronenz90"
 *   GITHUB_REPO     (var)    - e.g. "Cinema_find"
 *   ALLOWED_ORIGIN  (var, optional) - restrict CORS to your Pages origin,
 *                              e.g. "https://ronenz90.github.io"
 */

const GITHUB_API = "https://api.github.com";
const WATCHES_PATH = "config/watches.json";

export default {
  async fetch(request, env) {
    const corsHeaders = {
      "Access-Control-Allow-Origin": env.ALLOWED_ORIGIN || "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    };

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders });
    }

    if (request.method === "GET") {
      try {
        const watches = await getWatches(env);
        return jsonResponse(watches, 200, { ...corsHeaders, "Cache-Control": "no-store" });
      } catch (e) {
        return jsonResponse({ error: String(e.message || e) }, 500, corsHeaders);
      }
    }

    if (request.method !== "POST") {
      return jsonResponse({ error: "Method not allowed" }, 405, corsHeaders);
    }

    let payload;
    try {
      payload = await request.json();
    } catch {
      return jsonResponse({ error: "Invalid JSON body" }, 400, corsHeaders);
    }

    const { password, action } = payload;
    const hash = await sha256Hex(password || "");
    if (hash !== env.PASSWORD_HASH) {
      return jsonResponse({ error: "Unauthorized" }, 401, corsHeaders);
    }

    if (!["add", "edit", "delete"].includes(action)) {
      return jsonResponse({ error: "Invalid action" }, 400, corsHeaders);
    }

    try {
      const result = await updateWatches(env, action, payload);
      return jsonResponse({ ok: true, ...result }, 200, corsHeaders);
    } catch (e) {
      return jsonResponse({ error: String(e.message || e) }, 500, corsHeaders);
    }
  },
};

function jsonResponse(obj, status, corsHeaders) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json", ...corsHeaders },
  });
}

async function sha256Hex(text) {
  const data = new TextEncoder().encode(text);
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(hashBuffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

async function githubRequest(env, path, options = {}) {
  const url = `${GITHUB_API}/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "cinema-watcher-worker",
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`GitHub API ${res.status}: ${text}`);
  }
  return res.json();
}

function b64EncodeUnicode(str) {
  return btoa(unescape(encodeURIComponent(str)));
}

function b64DecodeUnicode(str) {
  return decodeURIComponent(escape(atob(str)));
}

async function getWatches(env) {
  const current = await githubRequest(env, `contents/${WATCHES_PATH}`);
  return JSON.parse(b64DecodeUnicode(current.content.replace(/\n/g, "")));
}

async function updateWatches(env, action, fields) {
  const current = await githubRequest(env, `contents/${WATCHES_PATH}`);
  let watches = JSON.parse(b64DecodeUnicode(current.content.replace(/\n/g, "")));

  let message;

  if (action === "add") {
    for (const r of ["cinema", "hall_type", "movie"]) {
      if (!fields[r]) throw new Error(`Missing field: ${r}`);
    }
    const newEntry = {
      id: `w-${Date.now()}`,
      cinema: fields.cinema,
      hall_type: fields.hall_type,
      movie: fields.movie,
      hour_from: (fields.hour_from || "00").padStart(2, "0"),
      hour_to: (fields.hour_to || "23").padStart(2, "0"),
    };
    if (fields.email) newEntry.email = fields.email;

    const isDup = watches.some(
      (w) => w.cinema === newEntry.cinema && w.hall_type === newEntry.hall_type && w.movie === newEntry.movie
    );
    if (isDup) return { skipped: "duplicate watch already exists" };

    watches.push(newEntry);
    message = `Add watch: ${newEntry.movie} @ ${newEntry.cinema}`;
  } else if (action === "edit") {
    if (!fields.id) throw new Error("Missing id");
    const target = watches.find((w) => w.id === fields.id);
    if (!target) throw new Error("Watch not found");
    if (fields.hour_from !== undefined) target.hour_from = (fields.hour_from || "00").padStart(2, "0");
    if (fields.hour_to !== undefined) target.hour_to = (fields.hour_to || "23").padStart(2, "0");
    if (fields.email !== undefined) {
      if (fields.email) target.email = fields.email;
      else delete target.email;
    }
    message = `Edit watch: ${target.movie} @ ${target.cinema}`;
  } else {
    if (!fields.id) throw new Error("Missing id");
    const before = watches.length;
    watches = watches.filter((w) => w.id !== fields.id);
    if (watches.length === before) throw new Error("Watch not found");
    message = `Delete watch id=${fields.id}`;
  }

  const newContentB64 = b64EncodeUnicode(JSON.stringify(watches, null, 2) + "\n");
  await githubRequest(env, `contents/${WATCHES_PATH}`, {
    method: "PUT",
    body: JSON.stringify({
      message,
      content: newContentB64,
      sha: current.sha,
    }),
  });

  return { action, count: watches.length };
}
