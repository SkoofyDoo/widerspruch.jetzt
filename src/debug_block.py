import os
from bs4 import BeautifulSoup

FILE = os.path.join("data", "raw", "31a_SGB_2_-_Einzelnorm.html")  # можно поменять на 31 тоже

html = open(FILE, "r", encoding="utf-8").read()
soup = BeautifulSoup(html, "lxml")

for tag in soup.find_all(["div", "article", "section", "main", "table"]):
    t = tag.get_text(" ", strip=True)
    if "(1)" in t and len(t) > 500:
        print("FOUND TAG:", tag.name, "| id=", tag.get("id"), "| class=", tag.get("class"))
        print("TEXT PREVIEW:\n", t[:800])
        print("\n---\n")
        break
else:
    print("No big block with (1) found")
