from app.generation.guards import (
    enforce_official_no_lists,
    find_strong_claims,
    guard_remove_anhoerung_para_for_krank_attest,
    guard_remove_work_context_if_not_in_user_text,
    hard_soften_strong_claims,
    sanitize_widerspruch_text,
    validate_text,
)


def test_hard_soften_strong_claims():
    text = "Der Bescheid ist unwirksam und offensichtlich rechtswidrig."
    flags = find_strong_claims(text)
    assert flags
    soft = hard_soften_strong_claims(text)
    assert "unwirksam" not in soft.lower()
    assert "offensichtlich" not in soft.lower()


def test_enforce_no_bullet_lists():
    body = "Erster Satz.\n- Punkt eins\n- Punkt zwei\nWeiterer Absatz."
    out = enforce_official_no_lists(body)
    assert "- Punkt" not in out
    assert "Punkt eins" in out


def test_work_context_guard():
    req = "Ich war krank und konnte den Termin nicht wahrnehmen. Attest liegt vor. Minderung 10%."
    letter = "Ich konnte meine Arbeit zu versehen nicht und verpasste den Termin."
    fixed = guard_remove_work_context_if_not_in_user_text(letter, req)
    assert "Arbeit zu versehen" not in fixed


def test_anhoerung_guard_for_krank_case():
    req = "krank Attest Termin Meldeversäumnis Minderung 10%"
    letter = (
        "Sehr geehrte Damen und Herren,\n\n"
        "Ich war krank.\n\n"
        "Ich verlange eine Anhörung nach § 24 SGB X.\n\n"
        "Mit freundlichen Grüßen"
    )
    fixed = guard_remove_anhoerung_para_for_krank_attest(letter, req)
    assert "§ 24" not in fixed or "Anhörung" not in fixed


def test_validate_requires_widerspruch_greeting():
    bad = "Hallo, das ist kein Brief."
    v = validate_text(bad)
    assert v["ok"] is False
    assert v["counts"]["errors"] >= 1

    good = (
        "Sehr geehrte Damen und Herren,\n\n"
        "hiermit lege ich Widerspruch ein.\n\n"
        "Mit freundlichen Grüßen"
    )
    v2 = validate_text(good)
    assert v2["ok"] is True


def test_sanitize_widerruf_to_widerspruch():
    t = sanitize_widerspruch_text("Ich will widerrufen den Bescheid.")
    assert "widerruf" not in t.lower() or "Widerspruch" in t
