import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from tqdm import tqdm

BASE = "https://www.sozialgesetzbuch-sgb.de/sgbx/"
START = urljoin(BASE, "1.html")

OUT_DIR = os.path.join("data", "raw", "sgbx")
os.makedirs(OUT_DIR, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def normalize_href(href: str) -> str:
    if not href:
        return ""
    href = href.strip()
    href = href.split("#")[0].split("?")[0]
    return href


def is_paragraph_page(href: str) -> bool:
    href = normalize_href(href)
    if not href.endswith(".html"):
        return False
    base = os.path.basename(urlparse(href).path)
    return bool(re.match(r"^\d+\.html$", base))


def fetch(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=30)
    print("FETCH", r.status_code, "|", r.url)
    r.raise_for_status()
    return r.text


def extract_links(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    links = []
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if is_paragraph_page(href):
            links.append(urljoin(BASE, normalize_href(href)))

    # сортируем по номеру 1..N
    links = sorted(set(links), key=lambda u: int(os.path.basename(urlparse(u).path).split(".")[0]))
    return links


def safe_filename(url: str, title: str) -> str:
    base = os.path.basename(urlparse(url).path)
    n = int(base.split(".")[0])
    t = re.sub(r"[^a-zA-Z0-9äöüÄÖÜß _\-]+", "", title).strip().replace(" ", "_")
    t = re.sub(r"_+", "_", t)[:120]
    return f"{n:03d}__SGBX_{n}_{t}.html"


def main():
    html = fetch(START)
    links = extract_links(html)

    # если вдруг на 1-й странице мало ссылок — попробуем собрать из первых 10 страниц
    if len(links) < 20:
        print("Low link count from START; scanning first 10 pages...")
        agg = set()
        for i in range(1, 11):
            page_html = fetch(urljoin(BASE, f"{i}.html"))
            for u in extract_links(page_html):
                agg.add(u)
        links = sorted(agg, key=lambda u: int(os.path.basename(urlparse(u).path).split(".")[0]))

    # если всё равно мало — можно просто качать диапазон
    if len(links) < 20:
        print("Still low links. Fallback: download pages 1..200 until 404.")
        links = []
        for i in range(1, 201):
            links.append(urljoin(BASE, f"{i}.html"))

    print(f"Found/Planned SGB X pages: {len(links)}")

    saved = 0
    for url in tqdm(links):
        try:
            page_html = fetch(url)
        except Exception:
            # для fallback режима (1..200) 404 означает "кончилось"
            break

        soup = BeautifulSoup(page_html, "lxml")
        title = soup.title.get_text(strip=True) if soup.title else url
        fname = safe_filename(url, title)

        with open(os.path.join(OUT_DIR, fname), "w", encoding="utf-8") as f:
            f.write(page_html)

        saved += 1

    print("Saved:", saved, "pages to", OUT_DIR)


if __name__ == "__main__":
    main()
