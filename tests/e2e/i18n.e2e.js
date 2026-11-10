// End-to-end check of languages: the header switcher, the remembered choice, the account's language
// (applied after login on a "new device"), fallbacks of untranslated pages. Runs against tests/e2e/fake-supabase.js.
// Run: python3 -m http.server 8765 (repo root) & node tests/e2e/i18n.e2e.js [http://localhost:8765]
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const assert = require("assert");

const BASE = process.argv[2] || "http://localhost:8765";
const FAKE = fs.readFileSync(path.join(__dirname, "fake-supabase.js"), "utf8");
const LANGS = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "..", "i18n", "languages.json"), "utf8")).languages;
const tree = (code) => { const l = LANGS.find((x) => x.code === code); return l.dir ? l.dir + "/" : ""; };

(async () => {
  const browser = await chromium.launch();
  const errors = [];
  let n = 0; const ok = (name) => console.log(`ok ${++n} - ${name}`);
  const watch = (p) => { p.on("pageerror", (e) => errors.push(e.message)); p.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); }); };

  // 1. a guest: every language tree builds; switching keeps the same page and is remembered
  const guest = await browser.newContext({ viewport: { width: 390, height: 860 } });
  const g = await guest.newPage(); watch(g);
  for (const l of LANGS) {
    await g.goto(`${BASE}/${tree(l.code)}m/f-power.html?lang=keep`, { waitUntil: "networkidle" });
    assert.strictEqual(await g.getAttribute("html", "lang"), l.htmlLang);
    assert.strictEqual(await g.getAttribute(`[data-lang-to="${l.code}"]`, "aria-current"), "true");
    const sw = await g.evaluate(() => document.documentElement.scrollWidth);
    assert.ok(sw <= 390, `${l.code}: scrollWidth ${sw}`);
  }
  ok("every language tree renders the module page, marks its language, no horizontal scroll at 390 px");

  await g.goto(`${BASE}/m/f-power.html`, { waitUntil: "networkidle" });
  const target = LANGS[1].code;
  await Promise.all([g.waitForURL(new RegExp(`/${tree(target)}m/f-power\\.html$`)), g.click(`[data-lang-to="${target}"]`)]);
  await g.goto(`${BASE}/index.html`);
  await g.waitForURL(new RegExp(`/${tree(target)}index\\.html$`));
  await g.goto(`${BASE}/pages/glossary.html#top`);
  await g.waitForURL(new RegExp(`/${tree(target)}pages/glossary\\.html#top$`));
  ok(`a chosen language (${target}) sticks: later links to the source tree open in ${target}`);

  await Promise.all([g.waitForURL(/\/m\/f-power\.html$|\/index\.html$|\/pages\/glossary\.html/), g.click(`[data-lang-to="${LANGS[0].code}"]`)]);
  assert.ok(!g.url().includes(`/${LANGS[1].dir}/`), g.url());
  ok("switching back to the source language works and is remembered");

  // 2. untranslated content says so and shows the original
  await g.goto(`${BASE}/${tree(target)}m/f-power.html?lang=keep`, { waitUntil: "networkidle" });
  const untranslated = await g.$("[data-untranslated]");
  const translated = fs.existsSync(path.join(__dirname, "..", "..", "i18n", target, "content", "foundation", "f-power.md"));
  assert.ok(translated ? !untranslated : !!untranslated, "untranslated notice must match the presence of a translation");
  ok("an untranslated module shows a notice and the original text; a translated one does not");

  // 3. the account's language follows the user to a new device
  const dev1 = await browser.newContext(); await dev1.addInitScript(FAKE);
  const a = await dev1.newPage(); watch(a); a.on("dialog", (d) => d.accept());
  await a.goto(`${BASE}/index.html`, { waitUntil: "networkidle" });
  await a.evaluate(() => window.__fakeSeed([{ id: "u-ola", email: "ola@example.org", username: "ola", password: "studentpass1", role: "student", created_at: "2026-11-01T00:00:00Z" }]));
  await a.goto(`${BASE}/pages/account.html`, { waitUntil: "networkidle" });
  await a.fill('[data-form="login"] [name=email]', "ola@example.org");
  await a.fill('[data-form="login"] [name=password]', "studentpass1");
  await a.click('[data-form="login"] gc-button[type=submit]');
  await a.waitForSelector('[data-acc="user"]:not([hidden])');
  // the first login stores the language in use (the source one); now pick another in the account settings
  await a.waitForFunction(() => JSON.parse(localStorage.getItem("fake-supabase-db")).users[0].lang === "ru");
  await Promise.all([a.waitForURL(new RegExp(`/${tree(target)}pages/account\\.html`)), a.selectOption("[data-acc-lang]", target)]);
  const stored = await a.evaluate(() => JSON.parse(localStorage.getItem("fake-supabase-db")).users[0].lang);
  assert.strictEqual(stored, target);
  ok("the account settings save the language in the profile and move the page to it");

  // "another device": a fresh browser without a stored choice, same backend data
  const db = await a.evaluate(() => localStorage.getItem("fake-supabase-db"));
  const dev2 = await browser.newContext(); await dev2.addInitScript(FAKE);
  await dev2.addInitScript((d) => { if (!localStorage.getItem("fake-supabase-db")) localStorage.setItem("fake-supabase-db", d); }, db);
  const b = await dev2.newPage(); watch(b);
  await b.goto(`${BASE}/pages/account.html`, { waitUntil: "networkidle" });
  assert.ok(!b.url().includes(`/${LANGS[1].dir}/`), "a guest on a new device starts in the source language");
  await b.fill('[data-form="login"] [name=email]', "ola@example.org");
  await b.fill('[data-form="login"] [name=password]', "studentpass1");
  await Promise.all([b.waitForURL(new RegExp(`/${tree(target)}pages/account\\.html`)), b.click('[data-form="login"] gc-button[type=submit]')]);
  await b.goto(`${BASE}/m/f-power.html`);
  await b.waitForURL(new RegExp(`/${tree(target)}m/f-power\\.html`));
  ok("on a new device the account's language is applied right after login and sticks");

  assert.deepStrictEqual(errors, [], "console errors: " + errors.join(" | "));
  ok("no console errors");
  await browser.close();
  console.log(`1..${n}`);
})().catch((e) => { console.error("not ok -", e.message); process.exit(1); });
