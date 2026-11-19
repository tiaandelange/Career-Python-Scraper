"""Static jobs dashboard (GitHub Pages). One self-contained HTML file with the job data inlined.

Only open jobs are written: closed links are deleted by the link checker before each build.
No personal data is published - just job titles, employers, locations, salaries and links.
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from pathlib import Path
from typing import Any

from job_scout.models.enums import WorkMode
from job_scout.models.job import CanonicalJobRecord
from job_scout.services.email_digest import job_excerpt, resolve_apply_url, salary_label
from job_scout.utils.dates import utcnow

logger = logging.getLogger(__name__)

EU_EEA = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT",
    "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE", "IS", "LI", "NO", "GB", "CH",
}


def region_of(job: CanonicalJobRecord) -> str:
    cc = (job.country_code or "").upper()
    if job.work_mode == WorkMode.REMOTE and not cc:
        return "Remote"
    if cc == "US":
        return "US"
    if cc == "ZA":
        return "South Africa"
    if cc in EU_EEA:
        return "Europe"
    if job.work_mode == WorkMode.REMOTE:
        return "Remote"
    return "Other"


def visa_status(job: CanonicalJobRecord) -> str:
    notes = (job.mobility.work_authorisation_notes or "").lower()
    if job.mobility.citizenship_required or "u.s. person" in notes or "citizenship requirement" in notes:
        return "citizens-only"
    if job.mobility.visa_sponsorship is True:
        return "green-card" if "green card" in notes else "sponsors"
    if job.mobility.visa_sponsorship is False:
        return "no-sponsor"
    from job_scout.services.scoring import sponsor_history

    if sponsor_history(job) is not None:
        return "history"
    return "unknown"


def _perm_count(job: CanonicalJobRecord) -> int:
    from job_scout.services.scoring import sponsor_history

    rec = sponsor_history(job)
    return rec.engineering_certified if rec else 0


def job_to_card(job: CanonicalJobRecord) -> dict[str, Any]:
    return {
        "id": job.canonical_fingerprint,
        "title": job.title,
        "company": job.company or "",
        "location": job.location_text or "",
        "region": region_of(job),
        "mode": job.work_mode.value,
        "score": job.fit_score or 0,
        "category": job.fit_category.value if job.fit_category else "",
        "salary": salary_label(job).replace("Salary: ", ""),
        "visa": visa_status(job),
        "perm": _perm_count(job),
        "firstSeen": job.first_seen_at.isoformat() if job.first_seen_at else None,
        "posted": job.date_posted.date().isoformat() if job.date_posted else None,
        "closing": job.closing_date.isoformat() if job.closing_date else None,
        "url": resolve_apply_url(job),
        "excerpt": job_excerpt(job, max_chars=260),
        "reasons": job.fit_reasons[:2],
    }


def group_locations(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One card per (title, company): the same role advertised in five cities is one job to apply for."""
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for card in sorted(cards, key=lambda c: -c["score"]):
        key = (" ".join(card["title"].lower().split()), card["company"].lower().strip())
        best = groups.get(key)
        if best is None:
            groups[key] = {**card, "otherLocations": []}
            continue
        loc = card["location"]
        if loc and loc != best["location"] and loc not in best["otherLocations"]:
            best["otherLocations"].append(loc)
        if (card["firstSeen"] or "") < (best["firstSeen"] or "~"):
            best["firstSeen"] = card["firstSeen"]
    return list(groups.values())


def build_dashboard(
    jobs: list[CanonicalJobRecord],
    out_dir: Path,
    *,
    min_score: int = 0,
    health: dict[str, Any] | None = None,
    tracking: dict[str, str] | None = None,
) -> dict[str, int]:
    cards = [
        job_to_card(job)
        for job in jobs
        if job.active and not job.rejected and job.fit_score is not None and job.fit_score >= min_score
    ]
    cards = group_locations(cards)
    cards.sort(key=lambda c: (-c["score"], c["title"]))
    now = utcnow()
    week_ago = (now - timedelta(days=7)).isoformat()
    stats = {
        "open": len(cards),
        "new_7d": sum(1 for c in cards if (c["firstSeen"] or "") >= week_ago),
        "us": sum(1 for c in cards if c["region"] == "US"),
        "sponsor": sum(1 for c in cards if c["visa"] in {"sponsors", "green-card", "history"}),
    }
    # Public Supabase URL + anon key only: row-level security limits job_status to the
    # signed-in user and every other table has no anon policies at all.
    meta = {"generated": now.isoformat(), "stats": stats, "health": health or {}, "tracking": tracking or None}
    out_dir.mkdir(parents=True, exist_ok=True)
    # Escape every "<" so scraped text can never close or open tags inside the inline <script>.
    data = json.dumps(cards, ensure_ascii=False, default=str).replace("<", "\\u003c")
    meta_json = json.dumps(meta, ensure_ascii=False, default=str).replace("<", "\\u003c")
    html = TEMPLATE.replace("__DATA__", data).replace("__META__", meta_json)
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")
    logger.info("Dashboard written to %s with %s open jobs", out_dir, len(cards))
    return stats


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Job Scout Board</title>
<style>
:root{--bg:#f6f7f5;--surface:#fff;--ink:#17201b;--muted:#5b665f;--line:#dfe4e0;--accent:#0f6b4c;--accent-soft:#e3f1ea;
--warn:#9a5b00;--warn-soft:#fff3dc;--bad:#a1263a;--bad-soft:#fde8ec;--blue:#1d4ed8;--blue-soft:#e8efff;--chip:#eef1ef}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0f1412;--surface:#171e1b;--ink:#e6ece8;--muted:#9aa8a0;
--line:#28322d;--accent:#4cc08f;--accent-soft:#16352a;--warn:#f0b54a;--warn-soft:#3a2c12;--bad:#f2788c;--bad-soft:#3b1a21;
--blue:#8fb0ff;--blue-soft:#1b2540;--chip:#212a26}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1040px;margin:0 auto;padding:20px 16px 48px}
header h1{margin:0;font-size:22px;letter-spacing:-.01em}
header p{margin:4px 0 0;color:var(--muted);font-size:13px}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:16px 0}
.stat{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.stat b{display:block;font-size:24px;line-height:1.1}
.stat span{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.controls{position:sticky;top:0;z-index:2;background:var(--bg);padding:8px 0 10px;border-bottom:1px solid var(--line);margin-bottom:12px}
.row{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-top:6px}
input[type=search]{width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:8px;background:var(--surface);color:var(--ink);font:inherit}
.chip{border:1px solid var(--line);background:var(--chip);color:var(--ink);border-radius:999px;padding:5px 11px;font:inherit;font-size:13px;cursor:pointer}
.chip[aria-pressed=true]{background:var(--accent);border-color:var(--accent);color:#fff}
.lbl{font-size:12px;color:var(--muted);margin-right:2px}
select{padding:5px 8px;border-radius:8px;border:1px solid var(--line);background:var(--surface);color:var(--ink);font:inherit;font-size:13px}
.count{font-size:13px;color:var(--muted);margin:4px 0 10px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin-bottom:10px}
.card.seen{opacity:.55}
.top{display:flex;gap:10px;justify-content:space-between;align-items:flex-start}
.card h2{margin:0;font-size:16px;line-height:1.3}
.card h2 a{color:var(--ink);text-decoration:none}
.card h2 a:hover{color:var(--accent);text-decoration:underline}
.score{flex:none;font-weight:700;font-size:13px;border-radius:8px;padding:4px 8px;background:var(--accent-soft);color:var(--accent)}
.meta{color:var(--muted);font-size:13px;margin:4px 0 8px}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px}
.tag{font-size:12px;border-radius:6px;padding:2px 8px;background:var(--chip)}
.tag.new{background:var(--blue-soft);color:var(--blue);font-weight:600}
.tag.v-sponsors,.tag.v-green-card,.tag.v-history{background:var(--accent-soft);color:var(--accent);font-weight:600}
.tag.v-no-sponsor,.tag.v-citizens-only{background:var(--bad-soft);color:var(--bad)}
.tag.closing{background:var(--warn-soft);color:var(--warn)}
.excerpt{margin:0 0 8px;font-size:14px}
.more{border-bottom:1px dotted var(--muted);cursor:help}
.why{margin:0 0 10px;font-size:13px;color:var(--muted)}
.actions{display:flex;gap:8px;flex-wrap:wrap}
.btn{display:inline-block;border-radius:8px;padding:7px 12px;font-size:13px;font-weight:600;text-decoration:none;border:1px solid var(--line);background:var(--surface);color:var(--ink);cursor:pointer;font-family:inherit}
.btn.primary{background:var(--accent);border-color:var(--accent);color:#fff}
.empty{padding:40px 16px;text-align:center;color:var(--muted)}
footer{margin-top:24px;font-size:12px;color:var(--muted)}
.track{display:flex;flex-wrap:wrap;gap:8px;align-items:center;background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin:0 0 12px;font-size:13px}
.track input[type=email]{flex:1 1 220px;padding:7px 10px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--ink);font:inherit}
.track .msg{color:var(--muted)}
.tabs{display:flex;gap:6px;margin-left:auto}
.st{font-size:13px}
.notes{flex:1 1 200px;min-width:0;padding:6px 9px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--ink);font:inherit;font-size:13px}
.card.s-applied,.card.s-interviewing,.card.s-offer{border-left:4px solid var(--accent)}
.card.s-saved{border-left:4px solid var(--blue)}
.card.s-rejected,.card.s-not_interested{border-left:4px solid var(--bad);opacity:.7}
.gone{font-size:12px;color:var(--warn)}
.actions .msg{font-size:12px;color:var(--muted);align-self:center}
@media (max-width:640px){.stats{grid-template-columns:repeat(2,1fr)}.card{padding:12px}.controls{position:static}}
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>Job Scout Board</h1>
  <p id="gen"></p>
</header>
<section class="stats" id="stats"></section>
<section class="track" id="track" hidden></section>
<section class="controls">
  <input type="search" id="q" placeholder="Search title, company, location..." aria-label="Search jobs">
  <div class="row" id="regions"><span class="lbl">Region</span></div>
  <div class="row" id="modes"><span class="lbl">Mode</span></div>
  <div class="row">
    <span class="lbl">Visa</span>
    <select id="visa" aria-label="Visa filter">
      <option value="all">Any</option>
      <option value="open">Hide "no sponsorship" / citizens-only</option>
      <option value="sponsor">Sponsors visas (stated or green-card history)</option>
    </select>
    <span class="lbl">Fit</span>
    <select id="fit" aria-label="Minimum fit">
      <option value="0">All</option><option value="60">Good+</option><option value="75">Strong+</option><option value="85">Exceptional</option>
    </select>
    <span class="lbl">Sort</span>
    <select id="sort" aria-label="Sort"><option value="score">Best fit</option><option value="new">Newest</option><option value="posted">Recently posted</option><option value="closing">Closing soon</option></select>
    <button class="chip" id="onlyNew" aria-pressed="false">New this week</button>
    <button class="chip" id="hideSeen" aria-pressed="false">Hide seen</button>
    <span class="lbl st-only" hidden>Status</span>
    <select id="statusFilter" class="st-only" aria-label="Application status filter" hidden>
      <option value="active">Hide not interested / rejected</option>
      <option value="all">All</option>
      <option value="untracked">Not tracked yet</option>
      <option value="saved">Saved</option><option value="applied">Applied</option>
      <option value="interviewing">Interviewing</option><option value="offer">Offer</option>
    </select>
  </div>
</section>
<div class="count" id="count"></div>
<main id="list"></main>
<footer id="foot"></footer>
</div>
<script>
const JOBS = __DATA__;
const META = __META__;
const $ = s => document.querySelector(s);
const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }
};
let seen = new Set(store.get("jobscout.seen", []));
const params = new URLSearchParams(location.search);
const state = {
  q: "", regions: new Set(), modes: new Set(), visa: store.get("jobscout.visa", "open"),
  fit: "0", sort: "score", onlyNew: params.get("new") === "1", hideSeen: store.get("jobscout.hideSeen", false),
  status: store.get("jobscout.statusFilter", "active"), view: "jobs"
};
const TRACK = META.tracking || null;
const STATUS = {saved: "Saved", applied: "Applied", interviewing: "Interviewing", offer: "Offer", rejected: "Rejected", not_interested: "Not interested"};
const HANDLED = new Set(["rejected", "not_interested"]);
let sb = null, user = null, statuses = new Map(), trackMsg = "";
const weekAgo = new Date(Date.now() - 7 * 864e5).toISOString();
const isNew = j => (j.firstSeen || "") >= weekAgo;
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmtDate = s => s ? new Date(s).toLocaleDateString(undefined, {day:"numeric", month:"short"}) : "";
const VISA = {"sponsors":"Sponsorship stated","green-card":"Green card / EB sponsorship","history":"Green-card sponsor history","no-sponsor":"No sponsorship","citizens-only":"Citizens / US persons only","unknown":"Visa: not stated"};

function chips(el, values, set) {
  for (const v of values) {
    const b = document.createElement("button");
    b.className = "chip"; b.textContent = v; b.setAttribute("aria-pressed", "false");
    b.onclick = () => { set.has(v) ? set.delete(v) : set.add(v); b.setAttribute("aria-pressed", String(set.has(v))); render(); };
    el.appendChild(b);
  }
}
function toggle(btn, key, persist) {
  btn.setAttribute("aria-pressed", String(state[key]));
  btn.onclick = () => { state[key] = !state[key]; btn.setAttribute("aria-pressed", String(state[key])); if (persist) store.set(persist, state[key]); render(); };
}

function filtered() {
  const q = state.q.trim().toLowerCase();
  let out = JOBS.filter(j => {
    if (q && !(`${j.title} ${j.company} ${j.location} ${(j.otherLocations || []).join(" ")}`.toLowerCase().includes(q))) return false;
    if (state.regions.size && !state.regions.has(j.region)) return false;
    if (state.modes.size && !state.modes.has(j.mode)) return false;
    if (state.visa === "open" && (j.visa === "no-sponsor" || j.visa === "citizens-only")) return false;
    if (state.visa === "sponsor" && !(j.visa === "sponsors" || j.visa === "green-card" || j.visa === "history")) return false;
    if (j.score < +state.fit) return false;
    if (state.onlyNew && !isNew(j)) return false;
    if (state.hideSeen && seen.has(j.id)) return false;
    if (user) {
      const st = statuses.get(j.id)?.status;
      if (state.status === "active" && HANDLED.has(st)) return false;
      if (state.status === "untracked" && st) return false;
      if (STATUS[state.status] && st !== state.status) return false;
    }
    return true;
  });
  if (state.sort === "new") out.sort((a, b) => (b.firstSeen || "").localeCompare(a.firstSeen || ""));
  else if (state.sort === "posted") out.sort((a, b) => (b.posted || "").localeCompare(a.posted || ""));
  else if (state.sort === "closing") out.sort((a, b) => (a.closing || "9999").localeCompare(b.closing || "9999"));
  return out;
}

function card(j) {
  const tags = [];
  if (isNew(j)) tags.push('<span class="tag new">New</span>');
  tags.push(`<span class="tag">${esc(j.mode)}</span>`);
  tags.push(`<span class="tag v-${j.visa}" ${j.perm ? `title="${j.perm} engineering PERM certifications (US Dept. of Labor)"` : ""}>${esc(VISA[j.visa])}${j.perm ? ` (${j.perm})` : ""}</span>`);
  if (j.salary) tags.push(`<span class="tag">${esc(j.salary)}</span>`);
  if (j.closing) tags.push(`<span class="tag closing">Closes ${esc(fmtDate(j.closing))}</span>`);
  const why = j.reasons && j.reasons.length ? `<p class="why">${esc(j.reasons.join(" · "))}</p>` : "";
  const isSeen = seen.has(j.id);
  const row = statuses.get(j.id);
  return `<article class="card${isSeen ? " seen" : ""}${row ? " s-" + row.status : ""}" data-id="${esc(j.id)}">
    <div class="top"><h2><a href="${esc(j.url)}" target="_blank" rel="noopener" data-open>${esc(j.title)}</a></h2>
    <span class="score" title="${esc(j.category)}">${j.score}</span></div>
    <div class="meta">${esc(j.company)} · ${esc(j.location || j.region)}${(j.otherLocations || []).length ? ` <span class="more" title="${esc(j.otherLocations.join(" · "))}">+${j.otherLocations.length} more location${j.otherLocations.length > 1 ? "s" : ""}</span>` : ""} · first seen ${esc(fmtDate(j.firstSeen))}${j.posted ? ` · posted ${esc(fmtDate(j.posted))}` : ""}</div>
    <div class="tags">${tags.join("")}</div>
    ${j.excerpt ? `<p class="excerpt">${esc(j.excerpt)}</p>` : ""}${why}
    <div class="actions"><a class="btn primary" href="${esc(j.url)}" target="_blank" rel="noopener" data-open>Open job</a>
    <button class="btn" data-seen>${isSeen ? "Mark unseen" : "Mark seen"}</button>${trackControls(j.id, row)}</div></article>`;
}

function trackControls(id, row) {
  if (!user) return "";
  const opts = [`<option value="">Track...</option>`].concat(
    Object.entries(STATUS).map(([k, v]) => `<option value="${k}"${row && row.status === k ? " selected" : ""}>${v}</option>`)).join("");
  const applied = row && row.applied_at ? ` <span class="msg">applied ${esc(fmtDate(row.applied_at))}</span>` : "";
  return `<select class="btn" data-status="${esc(id)}" aria-label="Application status">${opts}</select>` +
    (row ? `<input class="notes" data-notes="${esc(id)}" placeholder="Notes (contact, salary, follow-up...)" value="${esc(row.notes || "")}">${applied}` : "");
}

function appRow(r) {
  const j = JOBS.find(x => x.id === r.canonical_fingerprint);
  const url = (j && j.url) || r.url || "#";
  return `<article class="card s-${esc(r.status)}" data-id="${esc(r.canonical_fingerprint)}">
    <div class="top"><h2><a href="${esc(url)}" target="_blank" rel="noopener">${esc((j && j.title) || r.title || "Job")}</a></h2>
    ${j ? `<span class="score">${j.score}</span>` : `<span class="gone">no longer listed</span>`}</div>
    <div class="meta">${esc((j && j.company) || r.company || "")} · updated ${esc(fmtDate(r.updated_at))}</div>
    <div class="actions">${trackControls(r.canonical_fingerprint, r)}</div></article>`;
}

function render() {
  if (state.view === "apps" && user) {
    const rows = [...statuses.values()].sort((a, b) => (b.updated_at || "").localeCompare(a.updated_at || ""));
    $("#count").textContent = `${rows.length} tracked job${rows.length === 1 ? "" : "s"}`;
    $("#list").innerHTML = rows.length ? rows.map(appRow).join("") : '<div class="empty">Nothing tracked yet. Use "Track..." on a job.</div>';
    return;
  }
  const rows = filtered();
  $("#count").textContent = `${rows.length} of ${JOBS.length} open jobs`;
  $("#list").innerHTML = rows.length ? rows.map(card).join("") : '<div class="empty">No jobs match these filters.</div>';
}

function renderTrack() {
  const el = $("#track");
  if (!TRACK) { el.hidden = true; return; }
  el.hidden = false;
  document.querySelectorAll(".st-only").forEach(n => n.hidden = !user);
  if (!user) {
    el.innerHTML = `<b>Track applications</b><input type="email" id="email" placeholder="your@email" autocomplete="email" aria-label="Email for sign-in link">
      <button class="btn primary" id="signin">Email me a sign-in link</button><span class="msg">${esc(trackMsg)}</span>`;
    $("#signin").onclick = signIn;
    $("#email").onkeydown = e => { if (e.key === "Enter") signIn(); };
    return;
  }
  const counts = {};
  statuses.forEach(r => counts[r.status] = (counts[r.status] || 0) + 1);
  const summary = ["applied", "interviewing", "offer"].filter(k => counts[k]).map(k => `${counts[k]} ${STATUS[k].toLowerCase()}`).join(" · ");
  el.innerHTML = `<span>Tracking as <b>${esc(user.email)}</b>${summary ? " · " + esc(summary) : ""}</span>
    <span class="msg">${esc(trackMsg)}</span>
    <div class="tabs"><button class="chip" id="vJobs" aria-pressed="${state.view === "jobs"}">Open jobs</button>
    <button class="chip" id="vApps" aria-pressed="${state.view === "apps"}">My applications (${statuses.size})</button>
    <button class="btn" id="signout">Sign out</button></div>`;
  $("#vJobs").onclick = () => { state.view = "jobs"; renderTrack(); render(); };
  $("#vApps").onclick = () => { state.view = "apps"; renderTrack(); render(); };
  $("#signout").onclick = async () => { await sb.auth.signOut(); };
}

async function signIn() {
  const email = ($("#email").value || "").trim();
  if (!email) return;
  trackMsg = "Sending...";
  renderTrack();
  const { error } = await sb.auth.signInWithOtp({ email, options: { emailRedirectTo: location.origin + location.pathname } });
  trackMsg = error ? `Could not send link: ${error.message}` : "Check your email for the sign-in link.";
  renderTrack();
}

async function loadStatuses() {
  statuses = new Map();
  if (user) {
    const { data, error } = await sb.from("job_status").select("*");
    trackMsg = error ? `Could not load your tracking (${error.message})` : "";
    (data || []).forEach(r => statuses.set(r.canonical_fingerprint, r));
  }
  renderTrack();
  render();
}

async function saveStatus(id, status, notes) {
  const prev = statuses.get(id);
  const j = JOBS.find(x => x.id === id);
  if (!status) {
    statuses.delete(id);
    render(); renderTrack();
    const { error } = await sb.from("job_status").delete().eq("canonical_fingerprint", id);
    if (error) { statuses.set(id, prev); trackMsg = `Not saved: ${error.message}`; render(); renderTrack(); }
    return;
  }
  const today = new Date().toISOString().slice(0, 10);
  const row = {
    user_id: user.id, canonical_fingerprint: id, status,
    notes: notes !== undefined ? notes : (prev && prev.notes) || null,
    title: (j && j.title) || (prev && prev.title) || null,
    company: (j && j.company) || (prev && prev.company) || null,
    url: (j && j.url) || (prev && prev.url) || null,
    applied_at: (prev && prev.applied_at) || (["applied", "interviewing", "offer"].includes(status) ? today : null),
    updated_at: new Date().toISOString()
  };
  statuses.set(id, { ...(prev || {}), ...row });
  render(); renderTrack();
  const { error } = await sb.from("job_status").upsert(row, { onConflict: "user_id,canonical_fingerprint" });
  if (error) {
    if (prev) statuses.set(id, prev); else statuses.delete(id);
    trackMsg = `Not saved: ${error.message}`;
    render(); renderTrack();
  }
}

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const t = document.createElement("script");
    t.src = src; t.onload = resolve; t.onerror = reject;
    document.head.appendChild(t);
  });
}

async function initTracking() {
  if (!TRACK) return;
  renderTrack();
  try {
    await loadScript("https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/dist/umd/supabase.js");
    sb = window.supabase.createClient(TRACK.url, TRACK.key, { auth: { persistSession: true, detectSessionInUrl: true } });
    const { data } = await sb.auth.getSession();
    user = (data && data.session && data.session.user) || null;
    sb.auth.onAuthStateChange((_event, session) => {
      const before = user && user.id;
      user = (session && session.user) || null;
      if ((user && user.id) !== before) loadStatuses();
    });
    await loadStatuses();
  } catch (e) {
    trackMsg = "Tracking is unavailable right now.";
    renderTrack();
  }
}

$("#list").addEventListener("change", e => {
  const sel = e.target.closest("[data-status]");
  if (sel) { saveStatus(sel.dataset.status, sel.value); return; }
  const note = e.target.closest("[data-notes]");
  if (note) {
    const prev = statuses.get(note.dataset.notes);
    if (prev) saveStatus(note.dataset.notes, prev.status, note.value.trim() || null);
  }
});

$("#list").addEventListener("click", e => {
  const art = e.target.closest(".card"); if (!art) return;
  const id = art.dataset.id;
  if (e.target.closest("[data-seen]")) { seen.has(id) ? seen.delete(id) : seen.add(id); }
  else if (e.target.closest("[data-open]")) { seen.add(id); }
  else return;
  store.set("jobscout.seen", [...seen]);
  render();
});

const s = META.stats || {};
$("#stats").innerHTML = [["Open jobs", s.open], ["New this week", s.new_7d], ["In the US", s.us], ["Visa sponsors", s.sponsor]]
  .map(([l, v]) => `<div class="stat"><b>${v ?? 0}</b><span>${l}</span></div>`).join("");
$("#gen").textContent = `Updated ${new Date(META.generated).toLocaleString()} · closed links are removed automatically`;
const h = META.health || {};
$("#foot").textContent = h.sources_failed ? `Sources failing at last scrape: ${h.failed_sources.join(", ")}` : "";

const order = ["US", "South Africa", "Europe", "Remote", "Other"];
chips($("#regions"), order.filter(r => JOBS.some(j => j.region === r)), state.regions);
chips($("#modes"), ["remote", "hybrid", "onsite"].filter(m => JOBS.some(j => j.mode === m)), state.modes);
$("#visa").value = state.visa;
$("#visa").onchange = e => { state.visa = e.target.value; store.set("jobscout.visa", state.visa); render(); };
$("#fit").onchange = e => { state.fit = e.target.value; render(); };
$("#sort").onchange = e => { state.sort = e.target.value; render(); };
$("#q").oninput = e => { state.q = e.target.value; render(); };
toggle($("#onlyNew"), "onlyNew");
toggle($("#hideSeen"), "hideSeen", "jobscout.hideSeen");
$("#statusFilter").value = state.status;
$("#statusFilter").onchange = e => { state.status = e.target.value; store.set("jobscout.statusFilter", state.status); render(); };
render();
initTracking();
</script>
</body>
</html>
"""
