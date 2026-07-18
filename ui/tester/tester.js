// ui/tester/tester.js
// Mint tester token + run workflow (txt/pdf) end-to-end

const $ = (id) => document.getElementById(id);

const email = $("email");
const days = $("days");
const maxUses = $("max_uses");
const secret = $("secret");

const btnMint = $("btnMint");
const btnCopy = $("btnCopy");
const result = $("result");

// Optional: if you added these controls in tester UI (safe if missing)
const btnTestTxt = $("btnTestTxt");
const btnTestPdf = $("btnTestPdf");

let lastMint = null;

function setOut(obj) {
  const txt = typeof obj === "string" ? obj : JSON.stringify(obj, null, 2);
  result.textContent = txt;
  btnCopy.disabled = !txt || txt === "(noch nichts)";
}

async function readAsTextOrJson(res) {
  const text = await res.text();
  try { return JSON.parse(text); } catch (e) { return text; }
}

btnCopy?.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(result.textContent || "");
  } catch (e) {}
});

async function mintToken() {
  btnMint.disabled = true;
  setOut("Erstelle Token…");

  try {
    const q = new URLSearchParams({
      email: (email.value || "").trim(),
      days: String(parseInt(days.value || "14", 10)),
      max_uses: String(parseInt(maxUses.value || "30", 10))
    });

    const res = await fetch(`/tester/mint?${q.toString()}`, {
      method: "POST",
      headers: {
        "X-Admin-Secret": (secret.value || "").trim(),
      }
    });

    if (!res.ok) {
      const err = await readAsTextOrJson(res);
      setOut({ error: "Mint failed", status: res.status, details: err });
      return null;
    }

    const data = await readAsTextOrJson(res);
    lastMint = data;
    setOut(data);
    return data;
  } catch (e) {
    setOut({ error: String(e) });
    return null;
  } finally {
    btnMint.disabled = false;
  }
}

async function downloadFileFromResponse(res, fallbackName) {
  const blob = await res.blob();
  // try filename from Content-Disposition
  const cd = res.headers.get("Content-Disposition") || "";
  const m = cd.match(/filename="([^"]+)"/i);
  const filename = m?.[1] || fallbackName;

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

async function runWorkflow(format) {
  // Ensure we have token
  let mint = lastMint;
  if (!mint || !mint.workflow_url) {
    mint = await mintToken();
    if (!mint || !mint.workflow_url) return;
  }

  // Minimal payload for your /t/{token}/widerspruch/workflow
  // IMPORTANT: Adjust facts keys to what your main UI uses.
  const payload = {
    user_id: "tester",
    preview: false,
    format: format, // "txt" | "pdf"
    filename: format === "pdf" ? "widerspruch.pdf" : "widerspruch.txt",
    language: "de",
    style: "standard",
    include_quellen: false,
    include_context: false,
    k: 3,
    facts: {
      vorname: "Max",
      nachname: "Mustermann",
      kunden_nummer: "0123456789",
      jobcenter_id: "jc_berlin_charlottenburg_wilmersdorf",
      bescheid_datum: "2025-12-10",
      zugang_datum: "2025-12-12",
      bescheid_text: "Ich lege Widerspruch ein, da die Entscheidung aus meiner Sicht nicht nachvollziehbar ist. Bitte prüfen Sie die Berechnung und die Begründung."
    }
  };

  // Call workflow URL returned by mint
  setOut(`Starte Workflow (${format})…`);

  const res = await fetch(mint.workflow_url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  if (!res.ok) {
    const err = await readAsTextOrJson(res);
    setOut({ error: "Workflow failed", status: res.status, details: err, workflow_url: mint.workflow_url });
    return;
  }

  // If server returns file as attachment -> download
  const ct = (res.headers.get("Content-Type") || "").toLowerCase();
  const isFile = ct.includes("application/pdf") || ct.includes("text/plain");
  if (isFile && (format === "pdf" || format === "txt")) {
    await downloadFileFromResponse(res, payload.filename);
    setOut({ ok: true, downloaded: payload.filename, workflow_url: mint.workflow_url });
    return;
  }

  // If server returned JSON
  const data = await readAsTextOrJson(res);
  setOut(data);
}

btnMint.addEventListener("click", mintToken);

// If you have extra buttons in UI (recommended)
// <button id="btnTestTxt">Test TXT</button>
// <button id="btnTestPdf">Test PDF</button>
btnTestTxt?.addEventListener("click", () => runWorkflow("txt"));
btnTestPdf?.addEventListener("click", () => runWorkflow("pdf"));
