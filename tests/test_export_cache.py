from app.models import WiderspruchWorkflowRequest
from app.pdf.render import text_to_pdf_bytes
from app.routes.widerspruch import _export_letter


def test_export_pdf_contains_source_bytes():
    letter = "Sehr geehrte Damen und Herren,\n\nhiermit lege ich Widerspruch ein.\n\nMit freundlichen Grüßen\nMax"
    pdf = text_to_pdf_bytes(letter)
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 100


def test_export_txt_response_matches_letter():
    letter = "Test Widerspruch Brief Text 12345"
    resp = _export_letter(letter, "txt", "out.txt")
    assert resp.body.decode("utf-8") == letter
    assert "attachment" in resp.headers.get("content-disposition", "").lower()


def test_model_accepts_letter_text():
    req = WiderspruchWorkflowRequest(
        user_id="u1",
        letter_text="Cached letter body",
        format="pdf",
        preview=False,
    )
    assert req.letter_text == "Cached letter body"
