importScripts(new URL("pyodide/", self.location.href).toString() + "pyodide.js");

let pyodide = null;

const SETUP = `
import builtins as _py6_b

def _py6_input(prompt="", /):
    v = _py6_stdin(prompt)
    if v is None:
        raise EOFError("EOF when reading a line")
    return v

_py6_b.input = _py6_input
`;

function stdinPy6(prompt) {
  if (prompt) postMessage({ tipe: "prompt-teks", teks: String(prompt) });
  const sab = new SharedArrayBuffer(1 << 20);
  const i32 = new Int32Array(sab);
  postMessage({ tipe: "input", sab });
  while (Atomics.load(i32, 0) === 0) {
    Atomics.wait(i32, 0, 0, 500);
  }
  if (i32[0] === 2) return undefined;
  const salinan = new Uint8Array(sab, 16, i32[1]).slice();
  return new TextDecoder().decode(salinan);
}

async function muatPyodide() {
  const base = new URL("pyodide/", self.location.href).toString();
  pyodide = await loadPyodide({ indexURL: base });
  pyodide.globals.set("_py6_stdin", stdinPy6);
  postMessage({ tipe: "siap" });
}

function tangani(m) {
  switch (m.tipe) {
    case "jalan":
      if (!pyodide) {
        postMessage({ tipe: "galat", pesan: "Python belum siap." });
        return;
      }
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