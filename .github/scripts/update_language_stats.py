from __future__ import annotations

import json
import os
import re
import sys
from urllib.parse import quote
import urllib.error
import urllib.request
from pathlib import Path


USER = os.getenv("GITHUB_USER", "static2358")
TOKEN = os.getenv("GITHUB_TOKEN")
README = Path("README.md")
START = "<!-- LANGUAGE_STATS_START -->"
END = "<!-- LANGUAGE_STATS_END -->"

LANGUAGE_META = {
    "HTML": {"color": "E34F26", "logo": "html5", "logo_color": "white"},
    "Python": {"color": "3776AB", "logo": "python", "logo_color": "white"},
    "Java": {"color": "ED8B00", "logo": "openjdk", "logo_color": "white"},
    "JavaScript": {"color": "F7DF1E", "logo": "javascript", "logo_color": "111827"},
    "CSS": {"color": "1572B6", "logo": "css3", "logo_color": "white"},
    "C": {"color": "00599C", "logo": "c", "logo_color": "white"},
    "C++": {"color": "00599C", "logo": "cplusplus", "logo_color": "white"},
    "Shell": {"color": "4EAA25", "logo": "gnubash", "logo_color": "white"},
    "Makefile": {"color": "6D8086", "logo": "gnu", "logo_color": "white"},
    "Batchfile": {"color": "4D4D4D", "logo": "windowsterminal", "logo_color": "white"},
}
DEFAULT_COLORS = [
    "8B5CF6",
    "22D3EE",
    "10B981",
    "F97316",
    "EC4899",
    "A3E635",
    "FACC15",
]


def api_get(url: str) -> object:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "static2358-language-stats",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API error {exc.code} for {url}: {message}") from exc


def fetch_repos() -> list[dict]:
    repos: list[dict] = []
    page = 1
    while True:
        url = f"https://api.github.com/users/{USER}/repos?type=owner&sort=updated&per_page=100&page={page}"
        batch = api_get(url)
        if not isinstance(batch, list):
            raise RuntimeError("Unexpected GitHub API response while listing repos.")
        if not batch:
            break
        repos.extend(batch)
        page += 1
    return repos


def collect_language_bytes(repos: list[dict]) -> tuple[dict[str, int], int]:
    totals: dict[str, int] = {}
    scanned_repos = 0
    excluded_names = {USER.lower()}

    for repo in repos:
        name = str(repo.get("name", "")).lower()
        if repo.get("fork") or repo.get("archived") or name in excluded_names:
            continue

        languages_url = repo.get("languages_url")
        if not languages_url:
            continue

        languages = api_get(str(languages_url))
        if not isinstance(languages, dict) or not languages:
            continue

        scanned_repos += 1
        for language, byte_count in languages.items():
            if isinstance(language, str) and isinstance(byte_count, int):
                totals[language] = totals.get(language, 0) + byte_count

    return totals, scanned_repos


def language_color(language: str, index: int) -> str:
    return LANGUAGE_META.get(language, {}).get("color", DEFAULT_COLORS[index % len(DEFAULT_COLORS)])


def language_logo(language: str) -> str | None:
    logo = LANGUAGE_META.get(language, {}).get("logo")
    return str(logo) if logo else None


def language_logo_color(language: str) -> str:
    return str(LANGUAGE_META.get(language, {}).get("logo_color", "white"))


def sorted_percentages(totals: dict[str, int]) -> list[tuple[str, float]]:
    total_bytes = sum(totals.values())
    rows = sorted(totals.items(), key=lambda item: item[1], reverse=True)
    return [(language, byte_count / total_bytes * 100) for language, byte_count in rows]


def badge_url(language: str, percentage: float, index: int) -> str:
    params = {
        "label": language,
        "message": f"{percentage:.2f}%",
        "color": language_color(language, index),
        "style": "for-the-badge",
    }
    logo = language_logo(language)
    if logo:
        params["logo"] = logo
        params["logoColor"] = language_logo_color(language)

    query = "&".join(f"{key}={quote(value)}" for key, value in params.items())
    return f"https://img.shields.io/static/v1?{query}".replace("&", "&amp;")


def format_section(totals: dict[str, int], scanned_repos: int) -> str:
    if not totals:
        return "\n".join(
            [
                START,
                "No language data found yet.",
                END,
            ]
        )

    percentages = sorted_percentages(totals)

    lines = [
        START,
        "<!-- Auto-updated by .github/workflows/update-language-stats.yml -->",
        '<p align="center">',
    ]

    for index, (language, percentage) in enumerate(percentages):
        lines.append(f'  <img src="{badge_url(language, percentage, index)}" alt="{language} {percentage:.2f}%" />')

    lines.append("</p>")

    lines.append(END)
    return "\n".join(lines)


def update_readme(section: str) -> None:
    readme = README.read_text(encoding="utf-8")
    pattern = re.compile(f"{re.escape(START)}.*?{re.escape(END)}", re.DOTALL)
    updated, count = pattern.subn(section, readme)
    if count != 1:
        raise RuntimeError("Could not find exactly one language stats section in README.md.")
    README.write_text(updated, encoding="utf-8", newline="\n")


def main() -> int:
    repos = fetch_repos()
    totals, scanned_repos = collect_language_bytes(repos)
    update_readme(format_section(totals, scanned_repos))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
