importScripts(new URL("pyodide/", self.location.href).toString() + "pyodide.js");

let pyodide = null;

const ASAL = self.location.origin;

const SETUP = `
import builtins as _py6_b

def _py6_input(prompt="", /):
    v = _py6_stdin(prompt)
    if v is None:
        raise EOFError("EOF when reading a line")
    return v

_py6_b.input = _py6_input
`;

let kodeRuang = "";
let urutanInput = 0;

// input() sinkron tanpa SharedArrayBuffer (COOP/COEP tidak berlaku di HTTP/IP):
// 1. kirim "input" ke halaman utama agar papan input tampil.
// 2. blok worker via sync XHR ke server; server menahan request sampai
//    halaman utama mengirim jawaban ke /api/stdin/{kode}/jawab.
function stdinPy6(prompt) {
  if (prompt) postMessage({ tipe: "prompt-teks", teks: String(prompt) });
  const id = "k" + (++urutanInput);
  postMessage({ tipe: "input", id, prompt: prompt ? String(prompt) : "" });
  const xhr = new XMLHttpRequest();
  xhr.open("POST", ASAL + "/api/stdin/" + encodeURIComponent(kodeRuang), false);
  xhr.setRequestHeader("Content-Type", "application/json");
  xhr.send(JSON.stringify({ id }));
  let jawab = null;
  try {
    if (xhr.status === 200) jawab = JSON.parse(xhr.responseText);
  } catch (e) {
    jawab = null;
  }
  if (!jawab || jawab.eof) return undefined;
  return jawab.nilai == null ? "" : String(jawab.nilai);
}

async function resetStdin() {
  if (!kodeRuang) return;
  try {
    await fetch(ASAL + "/api/stdin/" + encodeURIComponent(kodeRuang) + "/reset", { method: "POST" });
  } catch (e) {}
}

async function muatPyodide() {
  const base = new URL("pyodide/", self.location.href).toString();
  pyodide = await loadPyodide({ indexURL: base });
  pyodide.globals.set("_py6_stdin", stdinPy6);
  postMessage({ tipe: "siap" });
}

async function tangani(m) {
  switch (m.tipe) {
    case "jalan":
      if (!pyodide) {
        postMessage({ tipe: "galat", pesan: "Python belum siap." });
        return;
      }
      kodeRuang = String(m.ruang || "").trim().toUpperCase();
      await resetStdin();
      const alir = (ch, galat) => {
        if (ch) postMessage({ tipe: "out", data: ch, galat: galat || false });
      };
      pyodide.setStdout({ batched: t => alir(t, false) });
      pyodide.setStderr({ batched: t => alir(t, true) });
      let ret;
      try {
        pyodide.runPython(SETUP);
        ret = pyodide.runPython(m.kode);
      } catch (e) {
        postMessage({ tipe: "galat", pesan: String(e && e.message || e) });
        return;
      }
      postMessage({
        tipe: "selesai",
        ret: ret === undefined || ret === null ? null : String(ret),
      });
      break;
  }
}

self.onmessage = (ev) => {
  if (ev.data.tipe === "muat") {
    muatPyodide().catch(e => postMessage({ tipe: "muat-gagal", pesan: String(e && e.message || e) }));
    return;
  }
  tangani(ev.data);
};