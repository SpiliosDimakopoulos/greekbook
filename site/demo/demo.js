// greekbook in the browser: the same Python converter as the CLI runs in
// Pyodide, and Typst runs as WebAssembly through typst.ts. Nothing leaves
// the page; there is no server.

const TYPST_TS = "0.7.0";
const PYODIDE = "0.27.7";
const CDN = "https://cdn.jsdelivr.net/npm/@myriaddreamin";

const $ = (id) => document.getElementById(id);
const manifest = await (await fetch("assets/manifest.json")).json();
let pyodide, convert, busy = false, queued = false, timer = null, lastSource = "";

function status(text, error = false) {
  $("status").textContent = text;
  $("status").classList.toggle("err", error);
}
function progress(fraction) {
  $("progress").style.width = `${Math.round(fraction * 100)}%`;
  if (fraction >= 1) setTimeout(() => ($("progress").style.width = "0"), 400);
}
const bytes = async (url) => new Uint8Array(await (await fetch(url)).arrayBuffer());

function loadScript(src, attrs = {}) {
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    Object.assign(s, {src, ...attrs});
    s.onload = resolve;
    s.onerror = () => reject(new Error(`Αποτυχία φόρτωσης ${src}`));
    document.head.append(s);
  });
}

async function loadPython() {
  status("Φόρτωση Python…");
  await loadScript(`https://cdn.jsdelivr.net/pyodide/v${PYODIDE}/full/pyodide.js`);
  pyodide = await globalThis.loadPyodide();
  progress(0.3);
  await pyodide.loadPackage(["pyyaml", "micropip"]);
  const micropip = pyodide.pyimport("micropip");
  await micropip.install(["markdown-it-py", "mdit-py-plugins"]);
  progress(0.45);
  pyodide.FS.mkdirTree("/src/greekbook");
  for (const name of manifest.python) {
    pyodide.FS.writeFile(`/src/greekbook/${name}`, await bytes(`assets/py/${name}`));
  }
  pyodide.runPython(await (await fetch("convert.py")).text());
  convert = pyodide.globals.get("convert");
}

async function loadTypst() {
  status("Φόρτωση Typst…");
  await loadScript(`${CDN}/typst.ts@${TYPST_TS}/dist/esm/contrib/all-in-one-lite.bundle.js`,
                   {type: "module", id: "typst"});
  const typst = globalThis.$typst;
  typst.setCompilerInitOptions({
    getModule: () => `${CDN}/typst-ts-web-compiler@${TYPST_TS}/pkg/typst_ts_web_compiler_bg.wasm`,
  });
  typst.setRendererInitOptions({
    getModule: () => `${CDN}/typst-ts-renderer@${TYPST_TS}/pkg/typst_ts_renderer_bg.wasm`,
  });
  const fonts = await Promise.all(manifest.fonts.map((f) => bytes(`assets/fonts/${f}`)));
  typst.use(globalThis.TypstSnippet.preloadFonts(fonts));
  for (const file of manifest.typst) {
    await typst.mapShadow(`/${file}`, await bytes(`assets/typst/${file}`));
  }
  await typst.mapShadow("/references.bib", await bytes("samples/references.bib"));
  progress(0.8);
}

async function loadSample(name) {
  $("text").value = await (await fetch(`samples/${name}.md`)).text();
  const m = $("text").value.match(/^template:\s*(\w+)/m);
  if (m) $("template").value = m[1];
}

async function render() {
  if (!convert) return;
  if (busy) { queued = true; return; }
  busy = true;
  const started = performance.now();
  status("Στοιχειοθεσία…");
  try {
    const result = convert($("text").value).toJs({dict_converter: Object.fromEntries});
    if (result.error) throw new Error(result.error);
    lastSource = result.source;
    const svg = await globalThis.$typst.svg({mainContent: lastSource});
    $("preview").innerHTML = svg;
    const pages = $("preview").querySelectorAll(".typst-page").length;
    status(`${pages} σελίδες · ${Math.round(performance.now() - started)} ms`);
    $("pdf").disabled = false;
  } catch (err) {
    status("Σφάλμα", true);
    const box = document.createElement("div");
    box.className = "message err";
    box.textContent = String(err.message || err).replace(/^Error:\s*/, "");
    $("preview").replaceChildren(box);
  } finally {
    busy = false;
    if (queued) { queued = false; render(); }
  }
}

$("text").addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(render, 350); });
$("sample").addEventListener("change", async () => {
  await loadSample($("sample").value);
  history.replaceState(null, "", `?sample=${$("sample").value}`);
  render();
});
$("template").addEventListener("change", () => {
  const t = $("text");
  t.value = /^template:.*$/m.test(t.value)
    ? t.value.replace(/^template:.*$/m, `template: ${$("template").value}`)
    : t.value.replace(/^---\n/, `---\ntemplate: ${$("template").value}\n`);
  render();
});
$("pdf").addEventListener("click", async () => {
  const pdf = await globalThis.$typst.pdf({mainContent: lastSource});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([pdf], {type: "application/pdf"}));
  a.download = "greekbook.pdf";
  a.click();
});

const initial = new URLSearchParams(location.search).get("sample") === "thesis" ? "thesis" : "novel";
$("sample").value = initial;

try {
  await loadSample(initial);
  await Promise.all([loadPython(), loadTypst()]);
  progress(1);
  $("text").disabled = false;
  await render();
} catch (err) {
  status("Σφάλμα φόρτωσης", true);
  $("preview").innerHTML = "";
  const box = document.createElement("div");
  box.className = "message err";
  box.textContent = String(err.message || err);
  $("preview").append(box);
}
