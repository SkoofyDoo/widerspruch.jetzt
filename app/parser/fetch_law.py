import os
import re
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from tqdm import tqdm
from typing import TypedDict, Literal

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

class Source(TypedDict):
    name: str
    base: str
    index: str
    out: str
    kind: Literal["gi"]

SOURCES: list[Source] = [
     {
        "name": "sgb2",
        "base": "https://www.gesetze-im-internet.de/sgb_2/",
        "index": "https://www.gesetze-im-internet.de/sgb_2/inhalts_bersicht.html",
        "out": os.path.join("data", "raw", "sgb2"),
        "kind": "gi",
    },
    {
        "name": "sgbx",
        "base": "https://www.gesetze-im-internet.de/sgb_10/",
        "index": "https://www.gesetze-im-internet.de/sgb_10/inhalts_bersicht.html",
        "out": os.path.join("data", "raw", "sgbx"),
        "kind": "gi",
    },
    {
        "name": "sgg",
        "base": "https://www.gesetze-im-internet.de/sgg/",
        "index": "https://www.gesetze-im-internet.de/sgg/inhalts_bersicht.html",
        "out": os.path.join("data", "raw", "sgg"),
        "kind": "gi",
    },
]


def normalize_href(href: str) -> str:
    if not href:
        return ""
    href = href.strip()
    href = href.split("#")[0].split("?")[0]
    return href


def is_gi_einzelnorm(href: str) -> bool:
    """gesetze-im-internet Einzelnorm links look like __1.html / __3a.html."""
    href = normalize_href(href)
    if not href.endswith(".html"):
        return False
    base = os.path.basename(urlparse(href).path)
    return bool(re.match(r"^__[\w]+\.html$", base))


def safe_filename(url: str, law_name: str) -> str:
    base = os.path.basename(urlparse(url).path).replace(".html", "")
    base = re.sub(r"[^a-zA-Z0-9_\-]+", "_", base).strip("_")[:120]
    return f"{law_name}__{base}.html"


def fetch(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=30)
    print("FETCH", r.status_code, "|", r.url)
    r.raise_for_status()
    return r.text


def extract_links(html: str, base: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    links = []
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if is_gi_einzelnorm(href):
            links.append(urljoin(base, normalize_href(href)))
    return sorted(set(links))


def fetch_law(source: Source) -> None:
    out = source["out"]
    os.makedirs(out, exist_ok=True)

    html = fetch(source["index"])
    links = extract_links(html, source["base"])

    if len(links) < 20:
        print("Low links from index, fallback to base:", source["base"])
        html2 = fetch(source["base"])
        links = sorted(set(links + extract_links(html2, source["base"])))

    print(f"[{source['name']}] pages: {len(links)}")
    if len(links) < 10:
        raise RuntimeError(f"Too few links for {source['name']}")

    for url in tqdm(links, desc=source["name"]):
        page = fetch(url)
        fname = safe_filename(url, source["name"])
        path = os.path.join(out, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(page)

    print(f"[{source['name']}] saved -> {out}")


if __name__ == "__main__":
    for s in SOURCES:
        fetch_law(s)

