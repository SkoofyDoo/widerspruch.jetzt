// ui/app.js
// WIDERSPRUCH.JETZT — UI logic (HTML-compatible ids + validation + preview/download + beta token + feedback gating)

(() => {
  const $ = (id) => document.getElementById(id);

  function getParam(name) {
    const p = new URLSearchParams(window.location.search);
    return p.get(name);
  }

  function toast(msg, ms = 2400) {
    const el = $("toast");
    if (!el) return;
    el.textContent = msg;
    el.classList.add("show");
    clearTimeout(toast._t);
    toast._t = setTimeout(() => el.classList.remove("show"), ms);
  }

  // ---------------------------
  // Feedback gating (only after N successful downloads)
  // ---------------------------
  const FEEDBACK_AFTER_USES = 10;
  const FEEDBACK_REMIND_AFTER_USES = 3;      // ✅ снова показать через N скачиваний, если нажали "Später"
  const FEEDBACK_COOLDOWN_USES = 999999;     // ✅ после "отправил" больше не показывать (можешь сделать меньше)
  const FEEDBACK_KEY_PREFIX = "wj_fb_";

  function feedbackKey() {
    const t = getParam("token") || "public";
    return FEEDBACK_KEY_PREFIX + t;
  }

  function getFeedbackState() {
    try {
      return JSON.parse(localStorage.getItem(feedbackKey()) || "{}");
    } catch {
      return {};
    }
  }
  function setFeedbackState(state) {
    localStorage.setItem(feedbackKey(), JSON.stringify(state || {}));
  }

  function incUseCount() {
    const st = getFeedbackState();
    st.uses = (Number(st.uses) || 0) + 1;
    st.has_downloaded_once = true;
    setFeedbackState(st);
    return st.uses;
  }

  function markFeedbackSent() {
    const st = getFeedbackState();
    st.last_sent_at = new Date().toISOString();
    st.last_sent_uses = Number(st.uses) || 0;
    setFeedbackState(st);
  }

  // ✅ “умная” логика показа:
  // - показываем после FEEDBACK_AFTER_USES
  // - если юзер нажал "Später", показываем снова через FEEDBACK_REMIND_AFTER_USES скачиваний
  // - если юзер отправил — не показываем (cooldown огромный)
  function shouldShowFeedbackNow() {
    const st = getFeedbackState();
    const uses = Number(st.uses) || 0;

    if (!st.has_downloaded_once) return false;
    if (uses < FEEDBACK_AFTER_USES) return false;

    const lastSentUses = Number(st.last_sent_uses) || 0;
    if (lastSentUses > 0 && (uses - lastSentUses) < FEEDBACK_COOLDOWN_USES) return false;

    const lastPromptUses = Number(st.last_prompt_uses) || 0;
    if (lastPromptUses > 0 && (uses - lastPromptUses) < FEEDBACK_REMIND_AFTER_USES) return false;

    return true;
  }

  function markPromptedThisUse() {
    const st = getFeedbackState();
    st.last_prompt_uses = Number(st.uses) || 0;
    st.last_prompt_at = new Date().toISOString();
    setFeedbackState(st);
  }

  // ---------------------------
  // Helpers
  // ---------------------------
  function onlyDigits(s) {
    return (s || "").replace(/\D+/g, "");
  }

  function setDisabled(el, disabled) {
    if (!el) return;
    const d = !!disabled;
    if (el.disabled !== d) el.disabled = d;
  }

  async function readTextOrJson(res) {
    const text = await res.text();
    try { return JSON.parse(text); } catch { return text; }
  }

  function filenameFromCD(cd, fallback) {
    const m = (cd || "").match(/filename="([^"]+)"/i);
    return (m && m[1]) ? m[1] : fallback;
  }

  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename || "download";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  function ensureUserId() {
    const key = "wj_user_id";
    let id = localStorage.getItem(key);
    if (!id) {
      id = (crypto?.randomUUID?.() || ("u_" + Math.random().toString(16).slice(2)));
      localStorage.setItem(key, id);
    }
    return id;
  }

  function withTimeout(ms) {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(new Error("timeout")), ms);
    return { signal: ctrl.signal, done: () => clearTimeout(t) };
  }

  function fmtTime(sec) {
    const s = Math.max(0, Math.floor(sec));
    const m = Math.floor(s / 60);
    const r = s % 60;
    return `${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
  }

  function isLikelyDownloadResponse(contentType, contentDisposition) {
    const ct = (contentType || "").toLowerCase();
    const cd = (contentDisposition || "").toLowerCase();
    // pdf/txt/octet-stream/attachment filename
    if (ct.includes("application/pdf")) return true;
    if (ct.includes("text/plain")) return true;
    if (ct.includes("application/octet-stream")) return true;
    if (cd.includes("attachment")) return true;
    if (cd.includes("filename=")) return true;
    return false;
  }

  // ---------------------------
  // Elements (MATCH HTML)
  // ---------------------------
  const el = {
    vorname: $("vorname"),
    nachname: $("nachname"),
    kunden: $("kunden_nummer"),
    jobcenter: $("jobcenter"),
    bescheid: $("bescheid_datum"),
    zugang: $("zugang_datum"),
    text: $("bescheid_text"),

    format: $("format"),
    include_quellen: $("include_quellen"),

    btnExample: $("btnExample"),
    btnPreview: $("btnPreview"),
    btnDownload: $("btnDownload"),
    ctaMobile: $("ctaMobile"),

    btnCopy: $("btnCopy"),
    btnClear: $("btnClear"),

    status: $("status"),
    statusText: $("statusText"),
    preview: $("preview"),

    paywallCta: $("paywallCta"),

    pillUser: $("pillUser"),
    pillAccess: $("pillAccess"),
  };

  const qm = {
    vor: $("qmVorname"),
    nach: $("qmNachname"),
    kund: $("qmKundenNummer"),
    jc: $("qmJobcenter"),
    bes: $("qmBescheidDatum"),
    zug: $("qmZugangDatum"),
  };

  // ---------------------------
  // Status + qmarks
  // ---------------------------
  function setStatus(kind, text) {
    if (!el.status || !el.statusText) return;

    el.status.classList.remove("info", "ok", "err", "bad", "warn");
    el.status.classList.add(kind === "bad" ? "err" : kind);

    el.statusText.textContent = text || "";
  }

  function setQMark(markEl, ok) {
    if (!markEl) return;
    markEl.classList.remove("ok", "bad");
    markEl.classList.add(ok ? "ok" : "bad");
    markEl.textContent = ok ? "✓" : "✕";
  }

  // ---------------------------
  // Feedback modal wiring
  // ---------------------------
  const fb = {
    modal: null,
    stars: null,
    quality: null,
    comment: null,
    role: null,
    submit: null,
    skip: null,
    checksWrap: null,
  };

  let fbRating = 0;
  let WHOAMI = null;

  function openFeedback() {
    if (!fb.modal) return;
    if (document.visibilityState !== "visible") return;
    fb.modal.hidden = false;
  }
  function closeFeedback() {
    if (!fb.modal) return;
    fb.modal.hidden = true;
  }
  function resetFeedback() {
    fbRating = 0;
    if (fb.stars) {
      [...fb.stars.querySelectorAll("[data-v]")].forEach((s) => s.classList.remove("active"));
    }
    if (fb.quality) fb.quality.value = "";
    if (fb.comment) fb.comment.value = "";
    if (fb.role) fb.role.value = "";
    if (fb.checksWrap) {
      [...fb.checksWrap.querySelectorAll('input[type="checkbox"]')].forEach((c) => { c.checked = false; });
    }
    if (fb.submit) fb.submit.disabled = true;
  }
  function validateFeedback() {
    const ok = fbRating > 0 && !!(fb.quality && fb.quality.value);
    if (fb.submit) fb.submit.disabled = !ok;
  }
  function getFeedbackIssues() {
    if (!fb.checksWrap) return [];
    return [...fb.checksWrap.querySelectorAll('input[type="checkbox"]:checked')].map((c) => c.value);
  }

  async function submitFeedback() {
    const payload = {
      rating: fbRating,
      quality: fb.quality ? fb.quality.value : "",
      issues: getFeedbackIssues(),
      comment: fb.comment ? fb.comment.value : "",
      role: fb.role ? fb.role.value : "",
      token: getParam("token") || null,
      email: (WHOAMI?.email || null),
      user_id: ensureUserId(),
      ua: navigator.userAgent,
      path: window.location.pathname + window.location.search,
      ts: new Date().toISOString(),
    };

    try {
      const res = await fetch("/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error("bad_response");
      return true;
    } catch {
      return false;
    }
  }

  function wireFeedback() {
    fb.modal = $("feedbackModal");
    fb.stars = $("fbStars");
    fb.quality = $("fbQuality");
    fb.comment = $("fbComment");
    fb.role = $("fbRole");
    fb.submit = $("fbSubmit");
    fb.skip = $("fbSkip");
    fb.checksWrap = document.querySelector(".checks");

    if (!fb.modal) return;

    closeFeedback();
    resetFeedback();

    fb.stars?.addEventListener("click", (e) => {
      const v = e.target?.dataset?.v;
      if (!v) return;
      fbRating = Number(v) || 0;
      [...fb.stars.querySelectorAll("[data-v]")].forEach((s) => {
        s.classList.toggle("active", Number(s.dataset.v) <= fbRating);
      });
      validateFeedback();
    });

    fb.quality?.addEventListener("change", validateFeedback);

    // ✅ "Später" = просто закрыть. Следующий показ будет через FEEDBACK_REMIND_AFTER_USES скачиваний.
    fb.skip?.addEventListener("click", () => {
      closeFeedback();
      resetFeedback();
    });

    fb.submit?.addEventListener("click", async () => {
      if (fb.submit.disabled) return;
      fb.submit.disabled = true;

      const ok = await submitFeedback();
      if (!ok) {
        fb.submit.disabled = false;
        toast("Feedback konnte nicht gesendet werden (offline?).");
        return;
      }

      markFeedbackSent();
      closeFeedback();
      resetFeedback();
      toast("Danke! Ihr Feedback wurde gesendet.");
    });
  }

  // ---------------------------
  // Beta token / endpoints
  // ---------------------------
  const betaToken = getParam("token");
  const BETA = !!betaToken;

  function workflowUrl() {
    if (BETA) return `/t/${encodeURIComponent(betaToken)}/widerspruch/workflow`;
    return `/widerspruch/workflow`;
  }

  // ---------------------------
  // Jobcenter loading
  // ---------------------------
  const JOBCENTER_FALLBACK = [
    { id: "jc_berlin_mitte", label: "Jobcenter Berlin Mitte" },
    { id: "jc_berlin_friedrichshain_kreuzberg", label: "Jobcenter Berlin Friedrichshain-Kreuzberg" },
    { id: "jc_berlin_pankow", label: "Jobcenter Berlin Pankow" },
    { id: "jc_berlin_charlottenburg_wilmersdorf", label: "Jobcenter Berlin Charlottenburg-Wilmersdorf" },
    { id: "jc_berlin_spandau", label: "Jobcenter Berlin Spandau" },
    { id: "jc_berlin_steeglitz_zehlendorf", label: "Jobcenter Berlin Steglitz-Zehlendorf" },
    { id: "jc_berlin_tempelhof_schoeneberg", label: "Jobcenter Berlin Tempelhof-Schöneberg" },
    { id: "jc_berlin_neukoelln", label: "Jobcenter Berlin Neukölln" },
    { id: "jc_berlin_treptow_koepenick", label: "Jobcenter Berlin Treptow-Köpenick" },
    { id: "jc_berlin_lichtenberg", label: "Jobcenter Berlin Lichtenberg" },
    { id: "jc_berlin_marzahn_hellersdorf", label: "Jobcenter Berlin Marzahn-Hellersdorf" },
    { id: "jc_berlin_reinickendorf", label: "Jobcenter Berlin Reinickendorf" },
  ];

  async function loadJobcenters() {
    if (!el.jobcenter) return;

    const setOptions = (items) => {
      el.jobcenter.innerHTML = "";
      const opt0 = document.createElement("option");
      opt0.value = "";
      opt0.textContent = "Bitte wählen…";
      el.jobcenter.appendChild(opt0);

      (items || []).forEach((x) => {
        const o = document.createElement("option");
        o.value = x.id;
        o.textContent = x.label;
        el.jobcenter.appendChild(o);
      });
    };

    const candidates = [
      "/jobcenters",
      "/jobcenter/list",
      "/ui/jobcenters.json",
    ];

    for (const url of candidates) {
      try {
        const res = await fetch(url, { cache: "no-store" });
        if (!res.ok) continue;
        const data = await res.json();
        if (Array.isArray(data) && data.length && data[0]?.id) {
          setOptions(data);
          return;
        }
      } catch {
        // ignore
      }
    }

    setOptions(JOBCENTER_FALLBACK);
  }

  // ---------------------------
  // Validation
  // ---------------------------
  let lastState = {
    allOk: false,
    values: {
      vorname: "",
      nachname: "",
      kunden_nummer: "",
      jobcenter: "",
      bescheid_datum: "",
      zugang_datum: "",
      bescheid_text: "",
      format: "txt",
      include_quellen: "false",
    },
    ok: {}
  };

  function computeValidation() {
    const vVor = (el.vorname?.value || "").trim();
    const vNach = (el.nachname?.value || "").trim();

    const cleaned = onlyDigits(el.kunden?.value || "");
    let next = cleaned;
    if (next.length > 10) next = next.slice(0, 10);
    if (el.kunden && el.kunden.value !== next) el.kunden.value = next;
    const vKund = (el.kunden?.value || "").trim();

    const vJc = (el.jobcenter?.value || "").trim();
    const vBes = (el.bescheid?.value || "").trim();
    const vZug = (el.zugang?.value || "").trim();
    const vTxt = (el.text?.value || "").trim();

    const ok = {
      vor: vVor.length >= 2,
      nach: vNach.length >= 2,
      kund: vKund.length === 10,
      jc: vJc.length > 0,
      bes: !!vBes,
      zug: !!vZug,
      txt: vTxt.length >= 20,
    };

    const allOk = ok.vor && ok.nach && ok.kund && ok.jc && ok.bes && ok.zug && ok.txt;

    return {
      allOk,
      ok,
      values: {
        vorname: vVor,
        nachname: vNach,
        kunden_nummer: vKund,
        jobcenter: vJc,
        bescheid_datum: vBes,
        zugang_datum: vZug,
        bescheid_text: vTxt,
        format: (el.format?.value || "txt"),
        include_quellen: (el.include_quellen?.value || "false"),
      }
    };
  }

  function applyValidation(st) {
    setQMark(qm.vor, st.ok.vor);
    setQMark(qm.nach, st.ok.nach);
    setQMark(qm.kund, st.ok.kund);
    setQMark(qm.jc, st.ok.jc);
    setQMark(qm.bes, st.ok.bes);
    setQMark(qm.zug, st.ok.zug);

    setDisabled(el.btnPreview, !st.allOk);
    setDisabled(el.ctaMobile, !st.allOk);

    // download only if beta and valid
    setDisabled(el.btnDownload, !(st.allOk && BETA));
  }

  function buildPayload(extra = {}) {
    const st = lastState.values;

    const fmt = (st.format || "txt").toLowerCase() === "pdf" ? "pdf" : "txt";
    const include_quellen = String(st.include_quellen || "false") === "true";

    return Object.assign({
      user_id: ensureUserId(),
      facts: {
        vorname: st.vorname,
        nachname: st.nachname,
        kunden_nummer: st.kunden_nummer,
        jobcenter_id: st.jobcenter,
        bescheid_datum: st.bescheid_datum,
        zugang_datum: st.zugang_datum,
        bescheid_text: st.bescheid_text,
      },
      k: 3,
      language: "de",
      style: "standard",
      include_quellen,
      include_context: false,
      preview: false,
      format: fmt,
    }, extra || {});
  }

  // ---------------------------
  // Example fill
  // ---------------------------
  function setExample() {
    if (!el.vorname || !el.nachname || !el.kunden || !el.jobcenter || !el.bescheid || !el.zugang || !el.text) {
      toast("UI-Elemente fehlen (IDs prüfen).");
      return;
    }
    el.vorname.value = "Max";
    el.nachname.value = "Mustermann";
    el.kunden.value = "1234567890";

    const wantJc = "jc_berlin_mitte";
    if ([...el.jobcenter.options].some(o => o.value === wantJc)) {
      el.jobcenter.value = wantJc;
    } else {
      setTimeout(() => {
        if ([...el.jobcenter.options].some(o => o.value === wantJc)) el.jobcenter.value = wantJc;
        onInput();
      }, 300);
    }

    el.bescheid.value = "2025-12-01";
    el.zugang.value = "2025-12-03";
    el.text.value = "Hiermit lege ich Widerspruch gegen den Bescheid ein. Die Leistungsminderung ist aus meiner Sicht nicht gerechtfertigt, da …";

    onInput();
    toast("Beispiel eingefügt.");
  }

  function clearAll() {
    if (el.vorname) el.vorname.value = "";
    if (el.nachname) el.nachname.value = "";
    if (el.kunden) el.kunden.value = "";
    if (el.jobcenter) el.jobcenter.value = "";
    if (el.bescheid) el.bescheid.value = "";
    if (el.zugang) el.zugang.value = "";
    if (el.text) el.text.value = "";
    if (el.format) el.format.value = "txt";
    if (el.include_quellen) el.include_quellen.value = "false";

    if (el.preview) el.preview.textContent = "(noch nichts)";
    if (el.paywallCta) el.paywallCta.style.display = "none";

    onInput();
    toast("Felder geleert.");
  }

  // ---------------------------
  // Preview
  // ---------------------------
  async function doPreview() {
    if (!lastState.allOk) {
      toast("Bitte Pflichtfelder ausfüllen.");
      return;
    }

    setDisabled(el.btnExample, true);
    setDisabled(el.btnPreview, true);
    setDisabled(el.ctaMobile, true);

    const startedAt = Date.now();
    setStatus("info", "Erzeuge Vorschau…");
    if (el.preview) el.preview.textContent = "⏳ Generiere Vorschau…";

    const timeout = withTimeout(90000);
    let tickT = null;

    try {
      tickT = setInterval(() => {
        const sec = Math.round((Date.now() - startedAt) / 1000);
        setStatus("info", `Erzeuge Vorschau… (${fmtTime(sec)})`);
      }, 900);

      const payload = buildPayload({ preview: true, format: "json" });
      const res = await fetch(workflowUrl(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: timeout.signal
      });

      const data = await readTextOrJson(res);
      if (!res.ok) {
        let msg = "Fehler";
        if (typeof data === "string" && data.trim()) msg = data;
        else if (data?.detail) msg = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
        else if (res.status === 502 || res.status === 503) {
          msg = `Server ${res.status}: RAG/LLM nicht bereit (oft: kein Index, OOM oder HF-Token). Prüfe /health und Railway Logs.`;
        } else {
          msg = `HTTP ${res.status}`;
        }
        setStatus("err", msg);
        toast(msg);
        if (el.preview) el.preview.textContent = msg;
        return;
      }

      setStatus("ok", "Vorschau bereit.");
      toast("Vorschau bereit.");
      if (el.preview) el.preview.textContent = (typeof data === "string") ? data : JSON.stringify(data, null, 2);

      if (!BETA && el.paywallCta) el.paywallCta.style.display = "block";
    } catch (e) {
      const msg =
        (e?.message === "timeout" || String(e).includes("timeout") || String(e).includes("AbortError"))
          ? "Zeitüberschreitung bei der Vorschau. Bitte erneut versuchen."
          : `Fehler: ${String(e)}`;

      setStatus("err", msg);
      toast(msg);
      if (el.preview) el.preview.textContent = msg;
    } finally {
      clearInterval(tickT);
      timeout.done();

      setDisabled(el.btnExample, false);
      setDisabled(el.btnPreview, !lastState.allOk);
      setDisabled(el.ctaMobile, !lastState.allOk);
    }
  }

  // ---------------------------
  // Download (beta only)
  // ---------------------------
  async function doDownload() {
    if (!lastState.allOk) {
      toast("Bitte Pflichtfelder ausfüllen.");
      return;
    }
    if (!BETA) {
      if (el.paywallCta) el.paywallCta.style.display = "block";
      toast("Bitte zuerst freischalten.");
      return;
    }

    const fmt = (lastState.values.format || "txt").toLowerCase() === "pdf" ? "pdf" : "txt";
    setDisabled(el.btnDownload, true);

    const startedAt = Date.now();
    setStatus("info", fmt === "pdf" ? "Erzeuge PDF…" : "Erzeuge TXT…");
    toast(fmt === "pdf" ? "PDF wird erstellt…" : "TXT wird erstellt…");

    const timeout = withTimeout(120000);

    try {
      const payload = buildPayload({ preview: false, format: fmt });
      const res = await fetch(workflowUrl(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: timeout.signal
      });

      if (!res.ok) {
        const err = await readTextOrJson(res);
        setStatus("err", "Download fehlgeschlagen.");
        toast("Download fehlgeschlagen.");
        if (el.preview) el.preview.textContent = (typeof err === "string") ? err : JSON.stringify(err, null, 2);
        return;
      }

      const ct = res.headers.get("Content-Type") || "";
      const cd = res.headers.get("Content-Disposition") || "";
      const fallback = fmt === "pdf" ? "widerspruch.pdf" : "widerspruch.txt";

      if (isLikelyDownloadResponse(ct, cd)) {
        const blob = await res.blob();
        const fname = filenameFromCD(cd, fallback);
        downloadBlob(blob, fname);

        const sec = Math.round((Date.now() - startedAt) / 1000);
        setStatus("ok", `Download gestartet (${sec}s).`);
        toast("Download gestartet.");

        // ✅ count only on real download
        incUseCount();

        // ✅ feedback after count
        if (fb.modal && shouldShowFeedbackNow()) {
          resetFeedback();
          setTimeout(() => {
            if (document.visibilityState !== "visible") return;
            markPromptedThisUse();
            openFeedback();
          }, 650);
        }
      } else {
        // Unexpected but ok response (e.g., json)
        const data = await readTextOrJson(res);
        setStatus("ok", "Antwort erhalten.");
        if (el.preview) el.preview.textContent = (typeof data === "string") ? data : JSON.stringify(data, null, 2);
      }
    } catch (e) {
      const msg =
        (e?.message === "timeout" || String(e).includes("timeout") || String(e).includes("AbortError"))
          ? "Zeitüberschreitung beim Download. Bitte erneut versuchen."
          : `Fehler beim Download: ${String(e)}`;

      setStatus("err", msg);
      toast(msg);
      if (el.preview) el.preview.textContent = msg;
    } finally {
      timeout.done();
      // ✅ вернуть кнопку в корректное состояние (а не всегда disabled)
      setDisabled(el.btnDownload, !(lastState.allOk && BETA));
    }
  }

  // ---------------------------
  // Whoami (beta) + ✅ sync local uses with server uses
  // ---------------------------
  async function loadWhoami() {
    if (!el.pillAccess || !el.pillUser) return;

    const b = el.pillUser.querySelector("b");
    if (b) b.textContent = "-";
    el.pillAccess.innerHTML = `<span class="dot"></span> Prüfe Zugang…`;

    if (!BETA) {
      el.pillAccess.innerHTML = `<span class="dot"></span> Kein Zugang`;
      return;
    }

    try {
      const res = await fetch(`/tester/whoami?token=${encodeURIComponent(betaToken)}`);
      if (!res.ok) {
        el.pillAccess.innerHTML = `<span class="dot"></span> Link ungültig`;
        return;
      }
      WHOAMI = await res.json();
      if (b) b.textContent = WHOAMI.email || "-";
      const uses = Number.isFinite(+WHOAMI.uses) ? WHOAMI.uses : "?";
      const max = Number.isFinite(+WHOAMI.max_uses) ? WHOAMI.max_uses : "?";
      el.pillAccess.innerHTML = `<span class="dot"></span> Beta aktiv (${uses}/${max})`;
      if (el.paywallCta) el.paywallCta.style.display = "none";

      // ✅ sync local feedback counter up to server counter
      try {
        const st = getFeedbackState();
        const serverUses = Number(WHOAMI?.uses) || 0;
        const localUses = Number(st.uses) || 0;

        if (serverUses > localUses) {
          st.uses = serverUses;
          if (serverUses > 0) st.has_downloaded_once = true;
          setFeedbackState(st);
        }
      } catch {
        // ignore
      }
    } catch {
      el.pillAccess.innerHTML = `<span class="dot"></span> Zugang unbekannt`;
    }
  }

  // ---------------------------
  // Input handler (debounced)
  // ---------------------------
  let onInputT = null;
  function onInput() {
    clearTimeout(onInputT);
    onInputT = setTimeout(() => {
      const st = computeValidation();
      lastState = st;
      applyValidation(st);
    }, 40);
  }

  // ---------------------------
  // Public config / demo banner
  // ---------------------------
  let APP_CFG = { demo_mode: false, demo_allow_download: false, payments_enabled: true };

  async function loadPublicConfig() {
    try {
      const res = await fetch("/config");
      if (!res.ok) return;
      APP_CFG = await res.json();
    } catch {
      return;
    }

    const banner = $("demoBanner");
    if (banner && APP_CFG.demo_mode && APP_CFG.demo_banner) {
      banner.hidden = false;
      banner.textContent = APP_CFG.demo_banner;
    }

    // Hide pricing/paywall noise in portfolio demo
    if (APP_CFG.demo_mode) {
      const pricing = $("linkPricing");
      if (pricing) pricing.style.display = "none";
      if (el.paywallCta) el.paywallCta.style.display = "none";
      if (el.pillAccess && !BETA) {
        el.pillAccess.innerHTML = `<span class="dot"></span> Demo (Preview frei)`;
      }
      // Download only if server allows it
      if (!APP_CFG.demo_allow_download && el.btnDownload) {
        el.btnDownload.title = "Download in DEMO_MODE deaktiviert — bitte Vorschau nutzen";
      }
    }
  }

  // ---------------------------
  // Init
  // ---------------------------
  async function init() {
    // ✅ Надёжная привязка событий (фикс: ручной ввод в textarea)
    const baseInputs = [
      el.vorname, el.nachname, el.kunden, el.jobcenter,
      el.bescheid, el.zugang, el.format, el.include_quellen
    ].filter(Boolean);

    baseInputs.forEach((node) => {
      node.addEventListener("input", onInput);
      node.addEventListener("change", onInput);
      node.addEventListener("blur", onInput);
    });

    if (el.text) {
      ["input", "change", "keyup", "paste", "blur"].forEach((evt) => {
        el.text.addEventListener(evt, onInput);
      });
    }

    el.btnExample?.addEventListener("click", setExample);
    el.btnPreview?.addEventListener("click", doPreview);
    el.btnDownload?.addEventListener("click", doDownload);
    el.ctaMobile?.addEventListener("click", doPreview);

    el.btnClear?.addEventListener("click", clearAll);

    // feedback
    wireFeedback();

    await loadPublicConfig();

    // jobcenters
    await loadJobcenters();

    // initial validation
    onInput();

    // whoami
    loadWhoami();

    if (!BETA && el.paywallCta && !APP_CFG.demo_mode) el.paywallCta.style.display = "none";

    setStatus("info", APP_CFG.demo_mode ? "Demo bereit (Preview ohne Zahlung)." : "Bereit.");
  }

  document.addEventListener("DOMContentLoaded", init);
})();
