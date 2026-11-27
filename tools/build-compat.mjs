// Übersetzt die moderne Quelldatei test/index.src.html in test/index.html, das auch auf
// iOS 12 / Safari 12 (z. B. iPhone 5s, iPhone 6) läuft.
//
//   cd tools && npm install && npm run build      -> schreibt ../test/index.html
//   npm run check                                  -> baut und prüft das Ergebnis auf Safari-12-Tauglichkeit
//
// Bearbeitet wird NUR test/index.src.html. test/index.html ist generiert und wird überschrieben.
// Was passiert:
//   JS   esbuild (Ziel safari12): ?. ?? usw. werden umgeschrieben; dazu kleine Polyfills (.at, allSettled, fromEntries)
//   CSS  inset, padding-block, clamp(), color-mix(), backdrop-filter, Flex-gap bekommen Ersatzregeln für alte Browser
//        (Flex-gap per Klasse "nfg" am <html>, die nur gesetzt wird, wenn der Browser es nicht kann)
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";
import { transformSync } from "esbuild";
import postcss from "postcss";

const dir = path.dirname(fileURLToPath(import.meta.url));
const seiten = [["../test/index.src.html", "../test/index.html"]];
const nurPruefen = process.argv.includes("--check");

/* ---------- Polyfills und Feature-Erkennung (bewusst ES5) ---------- */
const POLYFILLS = `<script>
/* Kompatibilität für ältere Browser (iOS 12): fehlende Funktionen ergänzen */
(function () {
  var def = function (o, n, f) { if (!o[n]) Object.defineProperty(o, n, { value: f, writable: true, configurable: true }); };
  def(Array.prototype, "at", function (i) { i = Math.trunc(i) || 0; if (i < 0) i += this.length; return i < 0 || i >= this.length ? undefined : this[i]; });
  def(String.prototype, "at", function (i) { i = Math.trunc(i) || 0; if (i < 0) i += this.length; return i < 0 || i >= this.length ? undefined : this.charAt(i); });
  def(Object, "fromEntries", function (it) { var o = {}; for (var e of it) o[e[0]] = e[1]; return o; });
  def(Promise, "allSettled", function (ps) {
    return Promise.all(Array.prototype.map.call(ps, function (p) {
      return Promise.resolve(p).then(function (value) { return { status: "fulfilled", value: value }; }, function (reason) { return { status: "rejected", reason: reason }; });
    }));
  });
  if (typeof globalThis === "undefined") window.globalThis = window;
  /* Flex-gap vorhanden? Sonst Klasse "nfg" setzen (CSS bringt dafür Abstände über margin) */
  try {
    var f = document.createElement("div"), a = document.createElement("div"), b = document.createElement("div");
    f.style.cssText = "display:flex;flex-direction:column;row-gap:1px;position:absolute;visibility:hidden";
    a.style.height = "1px"; b.style.height = "1px"; f.appendChild(a); f.appendChild(b);
    document.documentElement.appendChild(f);
    if (f.scrollHeight !== 3) document.documentElement.className += " nfg";
    document.documentElement.removeChild(f);
  } catch (e) { document.documentElement.className += " nfg"; }
})();
</script>
`;

/* ---------- CSS ---------- */
const wertTeile = v => {            // "a b(c d) e" -> ["a", "b(c d)", "e"]
  const out = []; let t = "", d = 0;
  for (const ch of v.trim()) {
    if (ch === "(") d++; if (ch === ")") d--;
    if (/\s/.test(ch) && d === 0) { if (t) out.push(t); t = ""; } else t += ch;
  }
  if (t) out.push(t);
  return out;
};
const klammerEnde = (s, i) => { let d = 0; for (let k = i; k < s.length; k++) { if (s[k] === "(") d++; if (s[k] === ")" && --d === 0) return k; } return -1; };
const kommaTeile = s => { const out = []; let t = "", d = 0; for (const ch of s) { if (ch === "(") d++; if (ch === ")") d--; if (ch === "," && d === 0) { out.push(t.trim()); t = ""; } else t += ch; } out.push(t.trim()); return out; };
// clamp(a,b,c) -> max(a,min(b,c))  (min/max kennt Safari ab 11.1, clamp erst ab 13.1)
const clampErsetzen = v => {
  let i;
  while ((i = v.indexOf("clamp(")) >= 0) {
    const e = klammerEnde(v, i + 5), [a, b, c] = kommaTeile(v.slice(i + 6, e));
    v = v.slice(0, i) + `max(${a},min(${b},${c}))` + v.slice(e + 1);
  }
  return v;
};
const hexRgb = h => { h = h.replace("#", ""); if (h.length === 3) h = [...h].map(c => c + c).join(""); return [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16)); };

function cssBauen(css) {
  const root = postcss.parse(css);
  const vars = {};
  root.walkRules(r => { if (r.selector.trim() === ":root") r.walkDecls(d => { if (d.prop.startsWith("--")) vars[d.prop] = d.value.trim(); }); });
  const farbe = v => {             // var(--x) / #hex -> [r,g,b] oder null
    v = v.trim(); let n = 0;
    while (v.startsWith("var(") && n++ < 5) { const m = v.match(/^var\((--[\w-]+)/); v = (vars[m[1]] || "").trim(); }
    return /^#[0-9a-f]{3}([0-9a-f]{3})?$/i.test(v) ? hexRgb(v) : null;
  };
  const mixRe = /color-mix\(\s*in srgb\s*,\s*(.+?)\s+(\d+(?:\.\d+)?)%\s*,\s*transparent\s*\)/;
  const mixErsatz = (v, c) => v.replace(new RegExp(mixRe.source, "g"), (_, x, p) => { const rgb = c || farbe(x); return rgb ? `rgba(${rgb.join(",")},${p / 100})` : "transparent"; });

  const farbRegeln = {};           // Selektor -> [r,g,b] für Regeln, die --c setzen
  root.walkRules(r => r.walkDecls("--c", d => { const c = farbe(d.value); if (c) r.selectors.forEach(s => { farbRegeln[s] = c; }); }));
  const flexLuecken = [], mixVarRegeln = [];

  root.walkRules(rule => {
    if (rule.parent?.type === "atrule" && /keyframes/.test(rule.parent.name)) return;
    const decl = {}; rule.walkDecls(d => { decl[d.prop] = d; });
    const anzeige = (decl.display?.value || "").trim();
    const flex = /(^|-)flex$/.test(anzeige);

    rule.walkDecls(d => {
      const p = d.prop;
      if (p === "backdrop-filter" && !decl["-webkit-backdrop-filter"]) d.cloneBefore({ prop: "-webkit-backdrop-filter" });
      if ((p === "mask-image" || p === "mask") && !decl["-webkit-" + p]) d.cloneBefore({ prop: "-webkit-" + p });
      if (/^(row-|column-)?gap$/.test(p) && !flex) d.cloneBefore({ prop: "grid-" + p });
      if (d.value.includes("clamp(")) d.value = clampErsetzen(d.value);
      if (mixRe.test(d.value) && !p.startsWith("--")) {
        if (/var\(--c\)/.test(d.value)) mixVarRegeln.push([rule, p, d.value]);
        else { const ers = mixErsatz(d.value); if (!ers.includes("transparent") || /rgba/.test(ers)) d.cloneBefore({ value: ers }); }
      }
    });

    if (flex && (decl.gap || decl["row-gap"] || decl["column-gap"])) {
      let zeile = "0", spalte = "0";
      if (decl.gap) { const t = wertTeile(decl.gap.value); zeile = t[0]; spalte = t[1] || t[0]; }
      if (decl["row-gap"]) zeile = decl["row-gap"].value;
      if (decl["column-gap"]) spalte = decl["column-gap"].value;
      flexLuecken.push({ rule, zeile, spalte, spalteRichtung: /column/.test(decl["flex-direction"]?.value || ""), umbruch: /wrap/.test(decl["flex-wrap"]?.value || "") || /wrap/.test(decl.flex?.value || ""), eigenerRand: !!(decl.margin || decl["margin-bottom"]) });
    }
  });

  // Flex-gap: Ersatz über margin, nur wenn <html class="nfg">
  for (const { rule, zeile, spalte, spalteRichtung, umbruch, eigenerRand } of flexLuecken) {
    const sel = rule.selectors, mit = suffix => sel.map(s => `.nfg ${s}${suffix}`).join(",");
    const neu = [];
    if (spalteRichtung && !umbruch) neu.push(`${mit(">*+*")}{margin-top:${zeile}}`);
    else if (!umbruch) neu.push(`${mit(">*+*")}{margin-left:${spalte}}`);
    else { neu.push(`${mit(">*")}{margin-right:${spalte};margin-bottom:${zeile}}`, `${mit(">*:last-child")}{margin-right:0}`); }
    let anker = rule;
    for (const n of neu) { const r = postcss.parse(n).first; anker.after(r); anker = r; }
  }

  // color-mix mit var(--c): je Variante feste Farben, nur wenn der Browser color-mix nicht kennt
  if (mixVarRegeln.length) {
    const basen = {};
    for (const [rule, p, v] of mixVarRegeln) (basen[rule.selector] ||= []).push([p, v, rule]);
    const out = [];
    for (const [basis, eintraege] of Object.entries(basen)) {
      for (const [sel, c] of Object.entries(farbRegeln)) {
        if (sel !== basis && !sel.startsWith(basis + ".")) continue;
        out.push(`${sel}{${eintraege.map(([p, v]) => `${p}:${mixErsatz(v, c)}`).join(";")}}`);
      }
    }
    const at = postcss.parse(`@supports not (background:color-mix(in srgb,red 50%,transparent)){${out.join("")}}`);
    root.append(at);
  }
  return root.toString();
}

/* inset und logische Abstände (padding-block ...) in top/right/bottom/left umschreiben */
function logischeEigenschaften(css) {
  const root = postcss.parse(css);
  root.walkDecls(d => {
    const w = wertTeile(d.value), p = d.prop;
    if (p === "inset") {
      const [t, r = t, b = t, l = r] = w;
      d.cloneBefore({ prop: "top", value: t }); d.cloneBefore({ prop: "right", value: r });
      d.cloneBefore({ prop: "bottom", value: b }); d.cloneBefore({ prop: "left", value: l }); d.remove();
      return;
    }
    const m = p.match(/^(padding|margin)-(block|inline)$/);
    if (m) {
      const [a, b = a] = w, [s1, s2] = m[2] === "block" ? ["top", "bottom"] : ["left", "right"];
      d.cloneBefore({ prop: `${m[1]}-${s1}`, value: a }); d.cloneBefore({ prop: `${m[1]}-${s2}`, value: b }); d.remove();
    }
  });
  return root.toString();
}

/* ---------- Seite bauen ---------- */
function seiteBauen(quelle, ziel) {
  let html = fs.readFileSync(path.join(dir, quelle), "utf8");

  html = html.replace(/<style>([\s\S]*?)<\/style>/, (_, css) => `<style>${cssBauen(logischeEigenschaften(css))}</style>`);

  const skripte = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
  if (skripte.length !== 1) throw new Error(`Erwartet genau ein Inline-Skript, gefunden: ${skripte.length}`);
  const js = skripte[0][1];
  const res = transformSync(js, { target: "safari12", charset: "utf8", legalComments: "none", logLevel: "warning" });
  html = html.replace(skripte[0][0], () => `<script>${res.code}</script>`);

  // Polyfills vor alle anderen Skripte
  html = html.replace(/<script src=/, m => POLYFILLS + m);
  // Hinweis, dass die Datei generiert ist
  html = html.replace(/<!doctype html>\s*/i, m => `${m.trim()}\n<!-- GENERIERT aus ${path.basename(quelle)} durch tools/build-compat.mjs - nicht von Hand bearbeiten -->\n`);

  fs.writeFileSync(path.join(dir, ziel), html);
  console.log(`${quelle} -> ${ziel}  (${(html.length / 1024).toFixed(0)} KB)`);
  return { html, js: res.code };
}

/* ---------- Prüfung ---------- */
function pruefen({ html, js }, name) {
  const probleme = [];
  const tmp = path.join(dir, ".check.js");
  fs.writeFileSync(tmp, js);
  try { execFileSync("npx", ["es-check", "es2019", tmp], { cwd: dir, stdio: "pipe" }); }
  catch (e) { probleme.push("es-check: " + String(e.stdout || e.message).split("\n").slice(0, 6).join(" | ")); }
  fs.unlinkSync(tmp);
  const css = (html.match(/<style>([\s\S]*?)<\/style>/) || [, ""])[1].replace(/\/\*[\s\S]*?\*\//g, "");
  const rest = html.replace(/<script>[\s\S]*?<\/script>/g, "");
  const regeln = [
    [/\(\?<[=!]/, "Regex-Lookbehind (Safari < 16.4)", js],
    [/\?\.[a-zA-Z_$\[(]/, "optional chaining im HTML (inline-Handler)", rest],
    [/(?<![\w-])inset\s*:/, "CSS inset", css],
    [/(?<![\w-])(padding|margin)-(block|inline)/, "CSS logische Abstände", css],
    [/clamp\(/, "CSS clamp()", css.replace(/@supports[\s\S]*$/, "")],
    [/aspect-ratio|:has\(|:is\(|:where\(|@container|@layer/, "CSS ohne Safari-12-Unterstützung", css],
    [/\.replaceAll\(|\.matchAll\(|structuredClone|\bAbortSignal\.timeout|ResizeObserver|\.toSorted\(|\.findLast\(|Object\.hasOwn\(|\.replaceChildren\(/, "API ohne Safari-12-Unterstützung", js],
  ];
  for (const [re, was, text] of regeln) if (was && re.test(text)) probleme.push(`${was}: ${(text.match(re) || [""])[0]}`);
  // jede Flex-Regel mit gap braucht ihr .nfg-Gegenstück
  const flexMitGap = [...css.matchAll(/(?:^|})\s*([^{}@]+)\{([^{}]*display:\s*(?:inline-)?flex[^{}]*)\}/g)].filter(m => /[;{]\s*(row-|column-)?gap:/.test(";" + m[2]));
  const ohne = flexMitGap.filter(m => !css.includes(".nfg " + m[1].trim().split(",")[0].trim()));
  if (ohne.length) probleme.push("Flex-gap ohne .nfg-Ersatz: " + ohne.map(m => m[1].trim()).join(" ; "));
  console.log(`${name}: ${probleme.length ? "PROBLEME\n  - " + probleme.join("\n  - ") : "OK (Syntax ES2019, keine bekannten Safari-12-Stolpersteine)"}`);
  return probleme.length === 0;
}

let ok = true;
for (const [q, z] of seiten) { const r = seiteBauen(q, z); if (nurPruefen) ok = pruefen(r, z) && ok; }
process.exit(ok ? 0 : 1);
