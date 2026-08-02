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


def _click_and_select(page, dt_selector: str, dd_container_selector: str, option_text: str, timeout=5000) -> bool:
    """Open a knockout-style dropdown and click the <a> whose text matches option_text."""
    page.click(dt_selector, timeout=timeout)
    page.wait_for_timeout(400)
    option = page.locator(f"{dd_container_selector} ul li a", has_text=option_text).first
    try:
        option.wait_for(state="visible", timeout=timeout)
        option.click()
        return True
    except PWTimeout:
        return False


def scrape_showtimes(watch: Watch, headless: bool = True) -> Dict[str, List[str]]:
    """Returns {date_string: [time_string, ...]} for one cinema/hall/movie combo."""
    result: Dict[str, List[str]] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(locale="he-IL", viewport={"width": 1400, "height": 1000})
        page.goto(BASE_URL, wait_until="networkidle", timeout=30000)

        try:
            page.click("text=אישור", timeout=4000)
        except PWTimeout:
            pass

        ok = _click_and_select(page, "a.b-theater", ".b-theater-cont", watch.cinema)
        if not ok:
            raise RuntimeError(f"Could not select cinema '{watch.cinema}'")
        page.wait_for_timeout(1200)

        ok = _click_and_select(page, "a.b-venuetype", ".b-venuetype-cont", watch.hall_type, timeout=4000)
        if not ok:
            log.warning("Hall type '%s' not found for '%s' - continuing without it.", watch.hall_type, watch.cinema)
        page.wait_for_timeout(1200)

        page.click("a.b-movie")
        page.wait_for_timeout(300)
        try:
            page.locator("input.movie-search").fill(watch.movie, timeout=3000)
            page.wait_for_timeout(500)
        except PWTimeout:
            pass
        movie_link = page.locator(".b-movie-cont ul li a", has_text=watch.movie).first
        movie_link.wait_for(state="visible", timeout=5000)
        movie_link.click()
        page.wait_for_timeout(1200)

        seen_dates = set()
        while True:
            page.click("a.b-date", timeout=5000)
            page.wait_for_timeout(300)
            date_links = page.locator(".b-date-cont ul li a")
            count = date_links.count()
            next_date_text, next_index = None, None
            for i in range(count):
                t = (date_links.nth(i).inner_text() or "").strip()
                if t and t not in seen_dates:
                    next_date_text, next_index = t, i
                    break
            if next_date_text is None:
                break
            seen_dates.add(next_date_text)
            date_links.nth(next_index).click()
            page.wait_for_timeout(1200)

            page.click("a.b-time", timeout=5000)
            page.wait_for_timeout(300)
            hour_links = page.locator(".b-time-cont ul li a")
            times = sorted({
                (hour_links.nth(i).inner_text() or "").strip()
                for i in range(hour_links.count())
                if (hour_links.nth(i).inner_text() or "").strip()
            })
            if times:
                result[next_date_text] = times

            if len(seen_dates) > 60:
                break

        browser.close()
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
