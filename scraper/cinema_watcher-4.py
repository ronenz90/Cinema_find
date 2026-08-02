"""
Cinema City Showtime Watcher - GitHub Actions edition
======================================================
Reads watch requests from config/watches.json, scrapes cinema-city.co.il
for each one using a real (headless) browser, compares against the
previous run's results in state/state.json, and emails a summary of any
new dates/times via Gmail SMTP.

Designed to be run by .github/workflows/check-showtimes.yml on a
schedule. All paths are relative to the repository root.

Required environment variables (set as GitHub Actions secrets):
    GMAIL_ADDRESS        - the Gmail account used to send from
    GMAIL_APP_PASSWORD   - a Gmail "app password" (not your normal password)
    ALERT_RECIPIENT_EMAIL - where alerts should be sent

SELECTORS
---------
Uses the real CSS classes from cinema-city.co.il's Knockout.js booking
widget (.b-theater, .b-venuetype, .b-movie, .b-date, .b-time), taken from
the site's actual HTML source. If the site changes its markup, these will
need updating - run locally with PWDEBUG=1 or headless=False to inspect.
"""

import json
import logging
import os
import smtplib
from dataclasses import dataclass
from email.mime.text import MIMEText
from pathlib import Path
from typing import Dict, List

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("cinema_watcher")

BASE_URL = "https://www.cinema-city.co.il/"
REPO_ROOT = Path(__file__).resolve().parent.parent
WATCHES_FILE = REPO_ROOT / "config" / "watches.json"
STATE_FILE = REPO_ROOT / "state" / "state.json"


@dataclass
class Watch:
    cinema: str
    hall_type: str
    movie: str
    id: str = ""             # e.g. "issue-12", assigned when the watch was added
    hour_from: str = "00"    # only alert for showtimes at/after this hour (inclusive)
    hour_to: str = "23"      # only alert for showtimes at/before this hour (inclusive)
    email: str = ""          # per-watch recipient override; "" = use ALERT_RECIPIENT_EMAIL

    @property
    def key(self) -> str:
        return f"{self.cinema}|{self.hall_type}|{self.movie}"

    @property
    def recipient(self) -> str:
        return self.email or os.environ["ALERT_RECIPIENT_EMAIL"]


def time_in_range(time_str: str, hour_from: str, hour_to: str) -> bool:
    """Whether a 'HH:MM' showtime falls within [hour_from, hour_to] (inclusive,
    hour granularity). Supports overnight ranges, e.g. hour_from=22, hour_to=2."""
    try:
        hour = int(time_str.split(":")[0])
    except (ValueError, IndexError):
        return True  # if we can't parse it, don't filter it out
    hf, ht = int(hour_from), int(hour_to)
    if hf <= ht:
        return hf <= hour <= ht
    return hour >= hf or hour <= ht


def load_watches() -> List[Watch]:
    if not WATCHES_FILE.exists():
        log.warning("No %s found - nothing to check.", WATCHES_FILE)
        return []
    with open(WATCHES_FILE, encoding="utf-8") as f:
        raw = json.load(f)
    return [Watch(**w) for w in raw]


def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def scrape_showtimes(watch: Watch, headless: bool = True) -> Dict[str, List[str]]:
    """Returns {date_string: [time_string, ...]} for one cinema/hall/movie combo."""
    result: Dict[str, List[str]] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(locale="he-IL", viewport={"width": 1400, "height": 1000})
        try:
            # NOTE: we intentionally do NOT wait_until="networkidle" here - the
            # site has ongoing background requests (analytics, chat widgets,
            # etc.) that never let the network go fully idle, which used to
            # cause spurious 30s timeouts. Instead: wait for the DOM, then
            # wait for the actual booking widget trigger to appear.
            page.goto(BASE_URL, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_selector("a.b-theater", timeout=20000)

            try:
                page.click("text=אישור", timeout=4000)
            except PWTimeout:
                pass

            # --- 1. Select cinema, directly via the site's own Knockout view model ---
            # `self` in a browser page is the same as `window`, and the site
            # itself does `self.ticketsVM.theatersAll([...])`, confirming
            # ticketsVM is a real global. Setting selected.theater(...) etc.
            # directly is far more reliable than clicking through dropdowns -
            # it's exactly what the site's own click handlers do internally,
            # without any of the click-scope/timing flakiness we hit before.
            theater_result = page.evaluate(
                """
                (cinemaName) => {
                    const vm = window.ticketsVM;
                    const list = (vm.baseTheaters ? vm.baseTheaters() : []) || vm.theaters();
                    const match = list.find(t => t.Name === cinemaName);
                    if (!match) return { ok: false, available: list.map(t => t.Name) };
                    vm.selected.theater(match);
                    return { ok: true };
                }
                """,
                watch.cinema,
            )
            if not theater_result.get("ok"):
                raise RuntimeError(
                    f"Cinema '{watch.cinema}' not found. Available: {theater_result.get('available')}"
                )
            log.info("Selected cinema (via VM): %s", watch.cinema)

            # --- 2. Select hall type, once venueTypes() has loaded ---
            page.wait_for_function("() => !window.ticketsVM.isPreloading()", timeout=10000)
            venue_result = page.evaluate(
                """
                (hallType) => {
                    const vm = window.ticketsVM;
                    const list = vm.venueTypes ? vm.venueTypes() : [];
                    const match = list.find(v => v.Name === hallType);
                    if (!match) return { ok: false, available: list.map(v => v.Name) };
                    vm.selected.venueType(match);
                    return { ok: true };
                }
                """,
                watch.hall_type,
            )
            if venue_result.get("ok"):
                log.info("Selected hall type (via VM): %s", watch.hall_type)
            else:
                log.warning(
                    "Hall type '%s' not found for '%s' (available: %s) - continuing without it.",
                    watch.hall_type, watch.cinema, venue_result.get("available"),
                )

            # --- 3. Select movie, once movies() has loaded (poll: this list
            # loads via AJAX after venueType is set, timing varies) ---
            page.wait_for_function("() => !window.ticketsVM.isPreloading()", timeout=10000)
            movie_result = {"ok": False}
            for attempt in range(8):
                movie_result = page.evaluate(
                    """
                    (movieName) => {
                        const vm = window.ticketsVM;
                        const list = (vm.filteredMovies ? vm.filteredMovies() : []) || vm.movies();
                        const match = list.find(m => m.Name === movieName);
                        if (!match) return { ok: false, count: list.length };
                        vm.selected.movie(match);
                        return { ok: true };
                    }
                    """,
                    watch.movie,
                )
                if movie_result.get("ok"):
                    break
                page.wait_for_timeout(1000)
            if not movie_result.get("ok"):
                raise RuntimeError(
                    f"Movie '{watch.movie}' not found for {watch.cinema}/{watch.hall_type} "
                    f"(movie list had {movie_result.get('count', '?')} entries)"
                )
            log.info("Selected movie (via VM): %s", watch.movie)

            # --- 4. Poll for dates() to populate (another AJAX call, triggered
            # by the movie selection) ---
            dates = []
            for attempt in range(8):
                dates = page.evaluate("() => window.ticketsVM.dates ? window.ticketsVM.dates() : []")
                if dates:
                    break
                page.wait_for_timeout(1000)
            if not dates:
                debug_state = page.evaluate(
                    """
                    () => {
                        const vm = window.ticketsVM;
                        const safe = (fn) => { try { return fn(); } catch (e) { return `<error: ${e}>`; } };
                        return {
                            theater: safe(() => vm.selected.theater() && vm.selected.theater().Name),
                            venueType: safe(() => vm.selected.venueType() && vm.selected.venueType().Name),
                            movie: safe(() => vm.selected.movie() && vm.selected.movie().Name),
                            isPreloading: safe(() => vm.isPreloading()),
                        };
                    }
                    """
                )
                log.warning("No dates found after waiting. VM state: %s", debug_state)
            else:
                log.info("Found %d date(s): %s", len(dates), dates)

            # --- 5. For each date, select it and read the hours from
            # selected.movie().Dates (refreshed via AJAX per selected date) ---
            for date_str in dates:
                page.evaluate("(d) => window.ticketsVM.selected.date(d)", date_str)
                hours = []
                for attempt in range(6):
                    hours = page.evaluate(
                        """
                        () => {
                            const vm = window.ticketsVM;
                            const m = vm.selected.movie();
                            if (!m || !m.Dates) return [];
                            return m.Dates.map(d => d.Hour).filter(Boolean);
                        }
                        """
                    )
                    if hours:
                        break
                    page.wait_for_timeout(800)
                if hours:
                    result[date_str] = sorted(set(hours))
        finally:
            # Always save a screenshot of the final page state - hugely useful
            # for debugging selector issues without needing another log round-trip.
            try:
                debug_dir = REPO_ROOT / "debug_screenshots"
                debug_dir.mkdir(parents=True, exist_ok=True)
                safe_name = "".join(c if c.isalnum() else "_" for c in watch.key)[:100]
                page.screenshot(path=str(debug_dir / f"{safe_name}.png"), full_page=True)
            except Exception as e:
                log.warning("Could not save debug screenshot: %s", e)
            browser.close()
    log.info("Scrape result for %s: %d date(s) with showtimes", watch.key, len(result))
    return result


def diff_showtimes(old: Dict[str, List[str]], new: Dict[str, List[str]]):
    new_dates = [d for d in new if d not in old]
    new_times_by_date = {}
    for d, times in new.items():
        if d in old:
            added = [t for t in times if t not in old[d]]
            if added:
                new_times_by_date[d] = added
    return new_dates, new_times_by_date


def send_email(recipient: str, subject: str, body: str) -> None:
    sender = os.environ["GMAIL_ADDRESS"]
    password = os.environ["GMAIL_APP_PASSWORD"]

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)
    log.info("Email sent to %s: %s", recipient, subject)


def main() -> None:
    watches = load_watches()
    if not watches:
        return
    state = load_state()

    for watch in watches:
        log.info("Checking %s", watch.key)
        try:
            current = scrape_showtimes(watch)
        except Exception as e:
            log.error("Failed to scrape %s: %s", watch.key, e)
            continue

        if not current:
            log.warning("No showtimes found for %s - selectors may need adjusting.", watch.key)
            continue

        previous = state.get(watch.key, {})
        # Always diff/store the FULL (unfiltered) data so future comparisons
        # stay correct regardless of this watch's hour filter.
        new_dates, new_times = diff_showtimes(previous, current)
        state[watch.key] = current

        if not previous:
            continue  # first time seeing this watch: just establish a baseline, no email

        # Filter down to only the showtimes within this watch's requested hour range.
        qualifying_dates = {}
        for d in new_dates:
            times_in_range = [t for t in current[d] if time_in_range(t, watch.hour_from, watch.hour_to)]
            if times_in_range:
                qualifying_dates[d] = times_in_range

        qualifying_times = {}
        for d, times in new_times.items():
            times_in_range = [t for t in times if time_in_range(t, watch.hour_from, watch.hour_to)]
            if times_in_range:
                qualifying_times[d] = times_in_range

        if not qualifying_dates and not qualifying_times:
            continue

        lines = [
            f"נמצאו זמנים חדשים עבור: {watch.movie}",
            f"קולנוע: {watch.cinema} | אולם: {watch.hall_type}",
            f"טווח שעות שהוגדר: {watch.hour_from}:00–{watch.hour_to}:00",
            "",
        ]
        if qualifying_dates:
            lines.append("תאריכים חדשים:")
            for d, times in qualifying_dates.items():
                lines.append(f"  {d}: {', '.join(times)}")
        if qualifying_times:
            lines.append("שעות חדשות בתאריכים קיימים:")
            for d, times in qualifying_times.items():
                lines.append(f"  {d}: {', '.join(times)}")

        try:
            send_email(watch.recipient, f"סינמה סיטי - זמנים חדשים ל{watch.movie}", "\n".join(lines))
        except Exception as e:
            log.error("Failed to send email for %s: %s", watch.key, e)

    save_state(state)


if __name__ == "__main__":
    main()
