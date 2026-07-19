"""Generate docs/assets/demo-preview.gif — portfolio product-flow preview."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "docs" / "assets" / "demo-preview.gif"
OUT.parent.mkdir(parents=True, exist_ok=True)

W, H = 960, 540
BG = (11, 16, 32)
PANEL = (15, 23, 42)
ACCENT = (99, 102, 241)
OK = (34, 197, 94)
TEXT = (229, 231, 235)
MUTED = (156, 163, 175)
LINE = (40, 50, 70)


def font(size: int):
    for p in (
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
    ):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()


F_TITLE = font(28)
F_H1 = font(22)
F_BODY = font(16)
F_SMALL = font(13)
F_MONO = font(14)


def rounded_rect(draw, xy, r, fill, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=width)


def base_frame(step_label: str, step_n: int):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 56), fill=(15, 20, 36))
    d.ellipse((22, 16, 42, 36), fill=ACCENT)
    d.text((52, 14), "WIDERSPRUCH.JETZT", font=F_TITLE, fill=TEXT)
    d.text((320, 20), "Textentwurf in Amtsstil  ·  TXT/PDF", font=F_SMALL, fill=MUTED)
    rounded_rect(d, (W - 220, 14, W - 20, 42), 12, (40, 50, 90), ACCENT)
    d.text((W - 208, 19), "Live Demo · RAG + LLM", font=F_SMALL, fill=TEXT)
    d.text((24, 70), f"Step {step_n}/3  ·  {step_label}", font=F_SMALL, fill=OK)
    return im, d


def frame1():
    im, d = base_frame("Eingaben ausfüllen", 1)
    rounded_rect(d, (24, 100, 460, 500), 16, PANEL, LINE)
    d.text((44, 118), "Eingaben", font=F_H1, fill=TEXT)
    fields = [
        ("Vorname", "Max"),
        ("Nachname", "Mustermann"),
        ("BG-Nr.", "0123456789"),
        ("Jobcenter", "Berlin Mitte"),
        ("Bescheid", "2025-12-01"),
    ]
    y = 160
    for label, val in fields:
        d.text((44, y), label, font=F_SMALL, fill=MUTED)
        rounded_rect(d, (44, y + 18, 430, y + 48), 8, (8, 12, 24), LINE)
        d.text((56, y + 24), val, font=F_BODY, fill=TEXT)
        y += 58
    rounded_rect(d, (480, 100, 936, 420), 16, PANEL, LINE)
    d.text((500, 118), "Sachverhalt", font=F_H1, fill=TEXT)
    lines = [
        "Termin versäumt wegen Erkrankung.",
        "Ärztliches Attest liegt vor.",
        "Minderung der Leistungen um 10%.",
        "Bitte um Prüfung des wichtigen Grundes.",
    ]
    yy = 170
    for ln in lines:
        d.text((500, yy), "•  " + ln, font=F_BODY, fill=TEXT)
        yy += 36
    rounded_rect(d, (480, 440, 700, 500), 12, ACCENT)
    d.text((510, 458), "Vorschau erzeugen →", font=F_BODY, fill=TEXT)
    return im


def frame2():
    im, d = base_frame("RAG + LLM Pipeline", 2)
    rounded_rect(d, (80, 140, 880, 460), 18, PANEL, LINE)
    boxes = [
        (110, 200, 280, 300, "1. Retrieve", "Chroma · SGB II/X"),
        (320, 200, 490, 300, "2. Generate", "HF Instruct LLM"),
        (530, 200, 700, 300, "3. Guards", "Citations · Soft claims"),
        (740, 200, 910, 300, "4. Preview", "Amtsstil · TXT/PDF"),
    ]
    for x1, y1, x2, y2, t, s in boxes:
        rounded_rect(d, (x1, y1, x2, y2), 12, (8, 12, 24), ACCENT, 2)
        d.text((x1 + 16, y1 + 28), t, font=F_BODY, fill=TEXT)
        d.text((x1 + 16, y1 + 58), s, font=F_SMALL, fill=MUTED)
    d.text((285, 235), "→", font=F_H1, fill=OK)
    d.text((495, 235), "→", font=F_H1, fill=OK)
    d.text((705, 235), "→", font=F_H1, fill=OK)
    d.text(
        (120, 340),
        "Grounded on official law text · no invented § · document assistance only",
        font=F_BODY,
        fill=MUTED,
    )
    d.text((120, 390), "Generiere Vorschau…", font=F_H1, fill=ACCENT)
    return im


def frame3():
    im, d = base_frame("Vorschau des Widerspruchs", 3)
    rounded_rect(d, (80, 110, 880, 500), 16, PANEL, LINE)
    letter = [
        "Max Mustermann  ·  BG 0123456789",
        "An Jobcenter Berlin Mitte",
        "",
        "Betreff: Widerspruch gegen Bescheid vom 01.12.2025",
        "",
        "Sehr geehrte Damen und Herren,",
        "",
        "hiermit lege ich Widerspruch gegen den Bescheid ein.",
        "Ich war am Termin erkrankt; Attest liegt vor.",
        "Bitte prüfen Sie den wichtigen Grund und die Minderung.",
        "",
        "Ich bitte um Eingangsbestätigung und erneute Entscheidung.",
        "",
        "Mit freundlichen Grüßen",
        "Max Mustermann",
    ]
    y = 130
    for ln in letter:
        d.text((110, y), ln, font=F_MONO, fill=TEXT if ln else MUTED)
        y += 22
    rounded_rect(d, (640, 455, 860, 490), 10, (20, 80, 40), OK)
    d.text((660, 462), "Vorschau bereit", font=F_BODY, fill=OK)
    return im


def main():
    frames = [frame1(), frame2(), frame3()]
    frames[0].save(
        OUT,
        save_all=True,
        append_images=frames[1:],
        duration=[2200, 2400, 2800],
        loop=0,
        optimize=True,
    )
    print("wrote", OUT, "bytes", OUT.stat().st_size)


if __name__ == "__main__":
    main()
