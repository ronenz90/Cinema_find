"""
Indexes the movies currently listed on the Cinema City homepage ("now
showing") so the watch-request form on the GitHub Pages site can offer an
up-to-date autocomplete list. Writes docs/movies.json.

Unlike cinema_watcher.py, this does NOT need Playwright: the homepage's
movie cards (title, running time, rating, etc.) are rendered server-side
in the initial HTML - only the booking widget itself is JavaScript-driven.
A plain HTTP request + HTML parse is enough and much faster/cheaper to
run nightly.

Run by .github/workflows/index-movies.yml on a nightly schedule.
"""

import json
import logging
from pathlib import Path

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("index_movies")

BASE_URL = "https://www.cinema-city.co.il/"
REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = REPO_ROOT / "docs" / "movies.json"


def fetch_movie_titles() -> list[str]:
    resp = requests.get(BASE_URL, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    titles = []
    seen = set()
    for h2 in soup.select("div.movie-thumb h2"):
        title = h2.get_text(strip=True)
        if title and title not in seen:
            seen.add(title)
            titles.append(title)

    return titles


def main() -> None:
    titles = fetch_movie_titles()
    if not titles:
        log.warning("No movie titles found - leaving movies.json unchanged to avoid wiping a good list.")
        return

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(titles, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Wrote %d movie titles to %s", len(titles), OUTPUT_FILE)


if __name__ == "__main__":
    main()
