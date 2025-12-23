import os
from bs4 import BeautifulSoup

RAW_ROOT = os.path.join("data", "raw")
OUT_DIR = os.path.join("data", "cleaned")
os.makedirs(OUT_DIR, exist_ok=True)

BAD = [
    "Gesetze im Internet",
    "nichtamtliches Inhaltsverzeichnis",
    "Zum Seitenanfang",
    "Seite drucken",
    "Impressum",
    "Datenschutz",
    "Barrierefreiheit",
    "Suche",
    "zurück",
    "weiter",
    "Feedback-Formular",
]


def extract_main_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    main = soup.find("div", id="level2") or soup.find(id="content") or soup.body or soup
    text = main.get_text("\n", strip=True)

    lines = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        low = ln.lower()
        if any(b.lower() in low for b in BAD):
            continue
        lines.append(ln)

    return "\n".join(lines)


def main():
    html_files = []
    for root, _, files in os.walk(RAW_ROOT):
        for fn in files:
            if fn.endswith(".html"):
                html_files.append(os.path.join(root, fn))

    if not html_files:
        raise RuntimeError("Нет raw html. Сначала запусти fetch_sgb2.py / fetch_sgbx.py")

    for path in html_files:
        with open(path, "r", encoding="utf-8") as f:
            html = f.read()

        cleaned = extract_main_text(html)

        rel = os.path.relpath(path, RAW_ROOT)  # sgb2/xxx.html или sgbx/xxx.html
        out_fn = rel.replace(os.sep, "__").replace(".html", ".txt")

        with open(os.path.join(OUT_DIR, out_fn), "w", encoding="utf-8") as f:
            f.write(cleaned)

    print("Cleaned files:", len(html_files), "->", OUT_DIR)


if __name__ == "__main__":
    main()
