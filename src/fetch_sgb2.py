import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from tqdm import tqdm

BASE = "https://www.gesetze-im-internet.de/sgb_2/"
INDEX = urljoin(BASE, "inhalts_bersicht.html")
FALLBACK = BASE

OUT_DIR = os.path.join("data", "raw", "sgb2")
os.makedirs(OUT_DIR, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def safe_filename(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_\-äöüÄÖÜß]+", "_", s).strip("_")
    return s[:180] if len(s) > 180 else s


def normalize_href(href: str) -> str:
    if not href:
        return ""
    href = href.strip()
    href = href.split("#")[0].split("?")[0]
    return href


def is_einzelnorm_href(href: str) -> bool:
   
    href = normalize_href(href)
    if not href or not href.endswith(".html"):
        return False
    base = os.path.basename(urlparse(href).path)
    return bool(re.match(r"^__[\w]+\.html$", base))


def extract_links(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    links = []
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if is_einzelnorm_href(href):
            links.append(urljoin(BASE, normalize_href(href)))
    return sorted(set(links))


def fetch(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=30)
    print("FETCH", r.status_code, "|", r.url)
    r.raise_for_status()
    return r.text


def main():
    html = fetch(INDEX)
    links = extract_links(html)

    if len(links) < 20:
        print("Low link count from Inhaltsübersicht, trying fallback:", FALLBACK)
        html2 = fetch(FALLBACK)
        links2 = extract_links(html2)
        links = sorted(set(links + links2))

    print(f"Found SGB II pages: {len(links)}")
    if len(links) < 20:
        raise RuntimeError("Ссылок слишком мало — структура изменилась.")

    for url in tqdm(links):
        page = requests.get(url, headers=HEADERS, timeout=30)
        page.raise_for_status()

        soup = BeautifulSoup(page.text, "lxml")
        title = soup.title.get_text(strip=True) if soup.title else url

        fname = safe_filename(title) + ".html"
        with open(os.path.join(OUT_DIR, fname), "w", encoding="utf-8") as f:
            f.write(page.text)

    print("Saved to:", OUT_DIR)


if __name__ == "__main__":
    main()
