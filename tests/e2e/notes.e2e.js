// End-to-end check of bookmarks, notes and feedback (assets/notes.js, assets/user-data.js) in Chromium.
// Part 1: guest with accounts off (localStorage only) at desktop and 400 px. Part 2: signed in against
// tests/e2e/fake-supabase.js — guest notes go up at registration, come back after logout/login, a conflict keeps both
// texts, feedback reaches the staff list and its status reaches the author.
// Run: python3 -m http.server 8765 (repo root) & node tests/e2e/notes.e2e.js [http://localhost:8765]
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const assert = require("assert");

const BASE = process.argv[2] || "http://localhost:8765";
const FAKE = fs.readFileSync(path.join(__dirname, "fake-supabase.js"), "utf8");
const LESSON = "m/bf-pid.html";
const NOTES = "uav-student:notes:v1", MARKS = "uav-student:bookmarks:v1";

(async () => {
  const browser = await chromium.launch();
  const errors = [];
  const watch = (p) => { p.on("pageerror", (e) => errors.push(e.message)); p.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); }); };
  let n = 0; const ok = (name) => console.log(`ok ${++n} - ${name}`);
  const ls = (p, k) => p.evaluate((k) => JSON.parse(localStorage.getItem(k) || "{}"), k);
  const noSideScroll = async (p, w, what) => { const sw = await p.evaluate(() => document.documentElement.scrollWidth); assert.ok(sw <= w, `${what}: scrollWidth ${sw} > ${w}`); };

  for (const width of [1280, 400]) {
    const ctx = await browser.newContext({ viewport: { width, height: 900 }, acceptDownloads: true });
    const p = await ctx.newPage(); watch(p);
    await p.goto(`${BASE}/${LESSON}`, { waitUntil: "networkidle" });

    // bar, heading tools, shared anchors with the reading history
    assert.ok(await p.isVisible(".nb-bar"));
    const heads = await p.$$eval(".module-body h2 .nb-tools", (t) => t.length);
    assert.ok(heads > 3, "every h2 has tools");
    const firstId = await p.$eval(".module-body h2", (h) => h.id);
    assert.match(firstId, /^[a-z0-9-]{1,60}$/, "stable id from the build");
    assert.ok(!/^sec-\d+$/.test(firstId), "not a positional id");
    await p.evaluate(() => window.scrollTo(0, document.querySelectorAll(".module-body h2")[1].offsetTop + 10));
    await p.waitForTimeout(600);
    const hist = await ls(p, "uav-student:history:v1");
    assert.ok(hist.items[0].heading && !/[☆✎⚑]/.test(hist.items[0].heading), "history heading text has no button glyphs: " + hist.items[0].heading);
    ok(`${width}px: bar under the tags, tools in headings, history keeps clean heading text`);

    // bookmarks: lesson + one section
    await p.click(".nb-mark");
    assert.strictEqual(await p.getAttribute(".nb-mark", "aria-pressed"), "true");
    const secBtn = p.locator(".module-body h2 [data-nb-mark]").nth(1);
    await secBtn.click();
    assert.strictEqual(await secBtn.getAttribute("aria-pressed"), "true");
    const marks = await ls(p, MARKS);
    assert.deepStrictEqual(Object.keys(marks).sort(), ["bf-pid#", "bf-pid#" + (await p.locator(".module-body h2").nth(1).getAttribute("id"))].sort());
    ok(`${width}px: bookmark the lesson and a section`);

    // notes panel: whole lesson, autosave, counter near the limit, Escape returns focus
    const open = p.locator(".nb-bar button[aria-controls=nb-panel]");
    await open.click();
    assert.ok(await p.isVisible("#nb-panel"));
    await p.fill('#nb-panel .nb-note[data-anchor=""] textarea', "PID: P first, then D.\nI last.");
    assert.match(await p.textContent(".nb-status"), /Не сохранено/);
    await p.waitForFunction(() => /Сохранено в этом браузере/.test(document.querySelector(".nb-status").textContent));
    assert.strictEqual((await ls(p, NOTES))["bf-pid#"].body, "PID: P first, then D.\nI last.");
    await p.fill('#nb-panel .nb-note[data-anchor=""] textarea', "x".repeat(7500));
    assert.strictEqual(await p.textContent('#nb-panel .nb-note[data-anchor=""] .nb-counter'), "7500 / 8000");
    assert.strictEqual(await p.getAttribute('#nb-panel .nb-note[data-anchor=""] textarea', "maxlength"), "8000");
    await p.fill('#nb-panel .nb-note[data-anchor=""] textarea', "PID: P first, then D.");
    if (width < 1100) await noSideScroll(p, width, "lesson with the panel open");
    await p.keyboard.press("Escape");
    assert.ok(!(await p.isVisible("#nb-panel")));
    assert.strictEqual(await p.evaluate(() => document.activeElement.getAttribute("aria-controls")), "nb-panel");
    assert.strictEqual((await ls(p, NOTES))["bf-pid#"].body, "PID: P first, then D.", "closing flushes the pending save");
    // section note from the heading button
    const noteBtn = p.locator(".module-body h2 [data-nb-note]").nth(2);
    const anchor = await p.locator(".module-body h2").nth(2).getAttribute("id");
    await noteBtn.click();
    assert.strictEqual(await p.evaluate(() => document.activeElement.closest(".nb-note").getAttribute("data-anchor")), anchor);
    await p.keyboard.type("D-term: watch the motor temperature.");
    await p.waitForTimeout(800);
    assert.strictEqual((await ls(p, NOTES))["bf-pid#" + anchor].body, "D-term: watch the motor temperature.");
    assert.ok(await noteBtn.getAttribute("data-has") !== null);
    await p.keyboard.press("Escape");
    assert.ok(await noteBtn.evaluate((b) => b === document.activeElement), "focus back on the heading button");
    ok(`${width}px: notes panel — autosave, saved state, counter, section note, Escape`);

    // feedback for a guest: explained, link to the account page, modal, Escape
    await p.click(".nb-bar >> text=Сообщить разработчику");
    assert.ok(await p.isVisible("dialog.nb-dialog[open]"));
    assert.match(await p.textContent("dialog.nb-dialog"), /только вошедшие пользователи/);
    assert.ok((await p.getAttribute('dialog.nb-dialog a[href$="pages/account.html"]', "href")) !== null);
    assert.strictEqual(await p.evaluate(() => !!document.activeElement.closest("dialog")), true, "focus inside the dialog");
    if (width < 1100) await noSideScroll(p, width, "lesson with the dialog open");
    await p.screenshot({ path: path.join(process.env.SHOTS || "/tmp", `notes-dialog-${width}.png`) });
    await p.keyboard.press("Escape");
    assert.ok(!(await p.isVisible("dialog.nb-dialog")));
    await p.locator(".module-body h2 .nb-tools button").nth(2).click();       // section variant
    assert.match(await p.textContent("dialog.nb-dialog"), /раздел «/);
    await p.keyboard.press("Escape");
    await noSideScroll(p, width, "lesson");
    ok(`${width}px: feedback — guests see why sign-in is needed, dialog is modal and closes on Escape`);

    // progress page: lists, search, section filter, edit in place, delete, export
    await p.goto(`${BASE}/pages/progress.html#notes`, { waitUntil: "networkidle" });
    assert.strictEqual(await p.locator('[data-nb-list="bookmarks"] .nb-item').count(), 2);
    assert.strictEqual(await p.locator('[data-nb-list="notes"] .nb-item').count(), 2);
    assert.ok((await p.locator('[data-nb-list="notes"] select option').count()) >= 2, "section filter lists the sections present");
    await p.fill('[data-nb-list="notes"] input[type=search]', "temperature");
    assert.strictEqual(await p.locator('[data-nb-list="notes"] .nb-item').count(), 1);
    await p.fill('[data-nb-list="notes"] input[type=search]', "");
    const item = p.locator('[data-nb-list="notes"] .nb-item').filter({ hasText: "PID: P first" });
    await item.locator("button", { hasText: "открыть" }).click();
    await item.locator("textarea").fill("PID: P first, then D, then I.");
    await p.waitForTimeout(800);
    assert.strictEqual((await ls(p, NOTES))["bf-pid#"].body, "PID: P first, then D, then I.");
    const [dl] = await Promise.all([p.waitForEvent("download"), p.click('[data-nb-list="notes"] button:has-text(".md")')]);
    const text = fs.readFileSync(await dl.path(), "utf8");
    assert.match(dl.suggestedFilename(), /^uav-notes-\d{4}-\d\d-\d\d\.md$/);
    assert.match(text, /### .+\nPID: P first, then D, then I\./);
    assert.ok(!/^#{1,2} /m.test(text), "only ### headings in the export");
    await p.locator('[data-nb-list="bookmarks"] .nb-item button', { hasText: "убрать" }).first().click();
    assert.strictEqual(await p.locator('[data-nb-list="bookmarks"] .nb-item').count(), 1);
    await noSideScroll(p, width, "progress page");
    await p.screenshot({ path: path.join(process.env.SHOTS || "/tmp", `notes-progress-${width}.png`), fullPage: false });
    ok(`${width}px: progress page — bookmarks and notes lists, search, filter, edit in place, delete, .md export`);

    // account page (accounts off): compact lists, settings, feedback block
    await p.goto(`${BASE}/pages/account.html`, { waitUntil: "networkidle" });
    assert.strictEqual(await p.locator('[data-nb-list="notes"] .nb-item').count(), 2);
    assert.strictEqual(await p.locator('[data-nb-list="bookmarks"] .nb-item').count(), 1);
    assert.ok(await p.isVisible("[data-acc-feedback-empty]"));
    await p.check('[data-setting="notesPanel"]');
    assert.strictEqual((await ls(p, "uav-student:settings")).notesPanel, true);
    await noSideScroll(p, width, "account page");
    await p.screenshot({ path: path.join(process.env.SHOTS || "/tmp", `notes-account-${width}.png`), fullPage: true });
    await p.goto(`${BASE}/${LESSON}`, { waitUntil: "networkidle" });
    assert.strictEqual(await p.isVisible("#nb-panel"), width >= 1100, "notesPanel opens the panel on wide screens only");
    await p.screenshot({ path: path.join(process.env.SHOTS || "/tmp", `notes-lesson-${width}.png`) });
    ok(`${width}px: account page — compact lists, settings; notesPanel setting opens the panel`);
    await ctx.close();
  }

  // ------------------------------------------------------------------ old positional anchors ("sec-N", before build ids)
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const p = await ctx.newPage(); watch(p);
    await p.goto(`${BASE}/${LESSON}`, { waitUntil: "networkidle" });
    const H = await p.$$eval(".module-body h2, .module-body h3, .module-body h4.md-subheading",
                             (hs) => hs.map((h) => ({ id: h.id, text: window.UAVHistory.headingText(h).slice(0, 160) })));
    assert.ok(H.length > 8);
    assert.ok(H.every((h) => /^[a-z0-9-]{1,60}$/.test(h.id) && !/^sec-\d+$/.test(h.id)), "every section heading, after the diagnostics too, has a build id");
    await p.goto(`${BASE}/pages/progress.html`, { waitUntil: "networkidle" });   // leave the lesson: it saves history on pagehide
    // what an older version of the site left in this browser: positional anchors = N-th heading in document order
    await p.evaluate(({ H, NOTES, MARKS }) => {
      localStorage.setItem(MARKS, JSON.stringify({
        "bf-pid#sec-3": { m: "bf-pid", a: "sec-3", label: H[2].text, title: "PID", at: 1, dirty: false, srv: null },
        // the lesson changed since: this bookmark was made on what is now heading 5 (its text wins over the position)
        "bf-pid#sec-1": { m: "bf-pid", a: "sec-1", label: H[4].text, title: "PID", at: 1, dirty: false, srv: null },
        "bf-cli#sec-3": { m: "bf-cli", a: "sec-3", label: "", title: "CLI", at: 1, dirty: false, srv: null }
      }));
      localStorage.setItem(NOTES, JSON.stringify({
        "bf-pid#sec-2": { m: "bf-pid", a: "sec-2", label: H[1].text, title: "PID", body: "old note", at: 1, dirty: false, srv: null },
        "bf-pid#sec-2-copy-1": { m: "bf-pid", a: "sec-2-copy-1", label: H[1].text + " (copy)", title: "PID", body: "old copy", at: 1, dirty: false, srv: null }
      }));
      localStorage.setItem("uav-student:history:v1", JSON.stringify({ items: [{ id: "bf-pid", path: "m/bf-pid.html", title: "PID", anchor: "sec-1", heading: H[3].text, at: Date.now() }], last: "bf-pid" }));
    }, { H, NOTES, MARKS });
    // progress page lists still carry the old anchors: the link opens the lesson on the right heading
    await p.reload({ waitUntil: "networkidle" });
    const histLink = p.locator("[data-history-list] a").first();
    assert.match(await histLink.getAttribute("href"), /bf-pid\.html#sec-1$/);
    await histLink.click();
    await p.waitForLoadState("networkidle");
    await p.waitForFunction((id) => location.hash === "#" + id, H[3].id, { timeout: 5000 });
    const top = await p.evaluate((id) => document.getElementById(id).getBoundingClientRect().top, H[3].id);
    assert.ok(top > -5 && top < 200, `old #sec-1 lands on the heading saved with it (top ${top})`);
    ok("old #sec-N link from the progress page lands on the heading saved with it (the lesson changed), the address is fixed");

    // the lesson page migrated this lesson's rows, and only them
    const marks = await ls(p, MARKS), notes = await ls(p, NOTES);
    assert.deepStrictEqual(Object.keys(marks).sort(), ["bf-cli#sec-3", "bf-pid#" + H[2].id, "bf-pid#" + H[4].id].sort());
    assert.deepStrictEqual(Object.keys(notes).sort(), ["bf-pid#" + H[1].id, "bf-pid#" + H[1].id + "-copy-1"].sort());
    assert.strictEqual(notes["bf-pid#" + H[1].id].body, "old note");
    assert.strictEqual(await p.getAttribute(`[data-nb-mark="${H[2].id}"]`, "aria-pressed"), "true", "old sec-3 bookmark shows on heading 3");
    assert.strictEqual(await p.getAttribute(`[data-nb-mark="${H[4].id}"]`, "aria-pressed"), "true", "moved heading found by its text");
    assert.ok(await p.getAttribute(`[data-nb-note="${H[1].id}"]`, "data-has") !== null, "old sec-2 note shows on heading 2");
    await p.reload({ waitUntil: "networkidle" });
    assert.deepStrictEqual([await ls(p, MARKS), await ls(p, NOTES)], [marks, notes], "migration is idempotent");
    // a direct old link too
    await p.goto(`${BASE}/${LESSON}#sec-2`, { waitUntil: "networkidle" });
    await p.waitForFunction((id) => location.hash === "#" + id, H[1].id, { timeout: 5000 });   // nothing saved: by position
    // an in-page hash change to an old anchor is resolved too; an ordinary one is left to the browser
    await p.evaluate(() => { location.hash = "#sec-3"; });
    await p.waitForFunction((id) => location.hash === "#" + id, H[2].id, { timeout: 5000 });
    await p.evaluate((id) => { location.hash = "#" + id; }, H[5].id);
    await p.waitForTimeout(200);
    assert.strictEqual(await p.evaluate(() => location.hash), "#" + H[5].id);
    // the progress list now links to the new anchors
    await p.goto(`${BASE}/pages/progress.html`, { waitUntil: "networkidle" });
    const hrefs = await p.$$eval('[data-nb-list="bookmarks"] a[href*="bf-pid"]', (as) => as.map((a) => a.getAttribute("href")));
    assert.ok(hrefs.some((h) => h.endsWith("#" + H[2].id)) && !hrefs.some((h) => /#sec-\d+$/.test(h)), "bookmark links use the new ids: " + hrefs);
    ok("old sec-N notes, copies and bookmarks move to the heading ids on the lesson page (by text when the lesson changed), once");
    await ctx.close();
  }

  // ------------------------------------------------------------------ signed in (fake backend)
  {
    const ctx = await browser.newContext({ viewport: { width: 400, height: 860 } });
    await ctx.addInitScript(FAKE);
    const p = await ctx.newPage(); watch(p);
    const db = () => p.evaluate(() => JSON.parse(localStorage.getItem("fake-supabase-db") || "{}"));
    await p.goto(`${BASE}/${LESSON}`, { waitUntil: "networkidle" });
    await p.evaluate(() => window.__fakeSeed([{ id: "u-adam", email: "adam@example.org", username: "adam", password: "adminpassword1", role: "admin", created_at: "2026-11-01T00:00:00Z" }]));
    // guest work before registering
    await p.click(".nb-mark");
    await p.click(".nb-bar button[aria-controls=nb-panel]");
    await p.fill('#nb-panel .nb-note[data-anchor=""] textarea', "written as a guest");
    await p.keyboard.press("Escape");
    await p.goto(`${BASE}/pages/account.html`, { waitUntil: "networkidle" });
    await p.click('[data-tab="register"]');
    await p.fill('[data-form="register"] [name=email]', "nina@example.org");
    await p.fill('[data-form="register"] [name=username]', "nina");
    await p.fill('[data-form="register"] [name=password]', "ninapassword1");
    await p.click('[data-form="register"] gc-button[type=submit]');
    await p.waitForSelector('[data-acc="user"]:not([hidden])');
    await p.waitForFunction(() => { const d = JSON.parse(localStorage.getItem("fake-supabase-db")); return d.tables && (d.tables.user_notes || []).length === 1 && (d.tables.user_bookmarks || []).length === 1; }, null, { timeout: 8000 });
    ok("signed in: guest notes and bookmarks go up at registration");

    // a later edit is pushed; logout wipes the local copy; login brings it back
    await p.goto(`${BASE}/${LESSON}`, { waitUntil: "networkidle" });
    await p.click(".nb-bar button[aria-controls=nb-panel]");
    await p.fill('#nb-panel .nb-note[data-anchor=""] textarea', "edited while signed in");
    await p.waitForFunction(() => /Сохранено в аккаунте/.test(document.querySelector(".nb-status").textContent), null, { timeout: 8000 });
    assert.strictEqual((await db()).tables.user_notes[0].body, "edited while signed in");
    await p.goto(`${BASE}/pages/account.html`, { waitUntil: "networkidle" });
    await p.click("[data-acc-logout]");
    await p.waitForSelector('[data-acc="guest"]:not([hidden])');
    assert.deepStrictEqual(await ls(p, NOTES), {}, "logout wipes notes from this browser");
    await p.fill('[data-form="login"] [name=email]', "nina@example.org");
    await p.fill('[data-form="login"] [name=password]', "ninapassword1");
    await p.click('[data-form="login"] gc-button[type=submit]');
    await p.waitForFunction(() => /edited while signed in/.test(localStorage.getItem("uav-student:notes:v1") || ""), null, { timeout: 8000 });
    ok("signed in: edits are pushed, logout wipes the local copy, login restores it");

    const login = async (email, pw) => {
      await p.goto(`${BASE}/pages/account.html`, { waitUntil: "networkidle" });
      await p.fill('[data-form="login"] [name=email]', email);
      await p.fill('[data-form="login"] [name=password]', pw);
      await p.click('[data-form="login"] gc-button[type=submit]');
      await p.waitForSelector('[data-acc="user"]:not([hidden])');
    };
    const logout = async () => {
      await p.goto(`${BASE}/pages/account.html`, { waitUntil: "networkidle" });
      await p.click("[data-acc-logout]");
      await p.waitForSelector('[data-acc="guest"]:not([hidden])');
    };
    const editServer = (fn) => p.evaluate((src) => {
      const d = JSON.parse(localStorage.getItem("fake-supabase-db")); (0, eval)(src)(d); localStorage.setItem("fake-supabase-db", JSON.stringify(d));
    }, fn.toString());
    const editLocal = (fn) => p.evaluate((src) => {
      const l = JSON.parse(localStorage.getItem("uav-student:notes:v1") || "{}"); (0, eval)(src)(l); localStorage.setItem("uav-student:notes:v1", JSON.stringify(l));
    }, fn.toString());
    const serverNotes = async () => { const d = await db(); const nina = d.users.find((u) => u.username === "nina").id; return (d.tables.user_notes || []).filter((r) => r.user_id === nina); };

    // conflict at login: the server row changed (another device) while this browser has an unsynced edit -> both texts kept
    await editServer((d) => { d.tables.user_notes[0].body = "from the phone"; d.tables.user_notes[0].updated_at = new Date(Date.now() + 60000).toISOString(); });
    await editLocal((l) => { l["bf-pid#"].body = "from the laptop"; l["bf-pid#"].dirty = true; });
    await p.evaluate(() => window.UAVUserData.syncAll());
    const merged = (await ls(p, NOTES))["bf-pid#"].body;
    assert.match(merged, /^from the phone\n\n— копия с этого устройства, .+ —\nfrom the laptop$/);
    assert.strictEqual((await serverNotes()).find((r) => r.anchor === "").body, merged);
    ok("signed in: a conflict keeps both texts in one note");

    // too long to combine: the server note stays as it is, this device's text becomes its own note next to it
    await editServer((d) => { const r = d.tables.user_notes.find((x) => x.anchor === ""); r.body = "p".repeat(5000); r.updated_at = new Date(Date.now() + 120000).toISOString(); });
    await editLocal((l) => { l["bf-pid#"].body = "l".repeat(5000); l["bf-pid#"].dirty = true; });
    await p.evaluate(() => window.UAVUserData.syncAll());
    await p.waitForFunction(() => { const d = JSON.parse(localStorage.getItem("fake-supabase-db")); return d.tables.user_notes.some((r) => r.anchor === "copy-1"); }, null, { timeout: 8000 });
    let rows = await serverNotes();
    assert.strictEqual(rows.find((r) => r.anchor === "").body, "p".repeat(5000), "the other device's note is untouched");
    assert.strictEqual(rows.find((r) => r.anchor === "copy-1").body, "l".repeat(5000), "this device's text lives on the server as a copy");
    await editServer((d) => { d.tables.user_notes = d.tables.user_notes.filter((r) => r.anchor !== "copy-1"); });
    await editLocal((l) => { delete l["bf-pid#copy-1"]; });
    ok("signed in: a conflict too long to combine keeps both notes on the server");

    // conflict on a push between logins: another device saved after this page loaded -> merged, not overwritten
    await p.goto(`${BASE}/${LESSON}`, { waitUntil: "networkidle" });
    await editServer((d) => { const r = d.tables.user_notes.find((x) => x.anchor === ""); r.body = "tablet wrote this"; r.updated_at = new Date(Date.now() + 180000).toISOString(); });
    await p.click(".nb-bar button[aria-controls=nb-panel]");
    await p.fill('#nb-panel .nb-note[data-anchor=""] textarea', "laptop wrote this");
    await p.waitForFunction(() => { const d = JSON.parse(localStorage.getItem("fake-supabase-db")); const r = d.tables.user_notes.find((x) => x.anchor === ""); return /tablet wrote this[\s\S]*laptop wrote this/.test(r.body); }, null, { timeout: 10000 });
    await p.keyboard.press("Escape");
    ok("signed in: a push over a newer server version merges instead of overwriting");

    // a row synced under an old positional anchor: the lesson page moves it; the server ends with the new row only
    await editServer((d) => { const r = d.tables.user_notes.find((x) => x.anchor === ""); d.tables.user_notes.push(Object.assign({}, r, { anchor: "sec-1", label: "Теория", body: "synced under sec-1", updated_at: new Date(Date.now() + 240000).toISOString() })); });
    await p.evaluate(() => window.UAVUserData.syncAll());
    assert.strictEqual((await ls(p, NOTES))["bf-pid#sec-1"].dirty, false, "came down as a clean synced row");
    await p.goto(`${BASE}/${LESSON}`, { waitUntil: "networkidle" });
    await p.waitForFunction(() => window.UAVUserData.pending() === 0, null, { timeout: 8000 });
    rows = await serverNotes();
    assert.ok(!rows.some((r) => r.anchor === "sec-1"), "the old server row is gone");
    assert.strictEqual(rows.find((r) => r.anchor === "teoriya").body, "synced under sec-1");
    assert.ok(!Object.keys(await ls(p, NOTES)).some((k) => /#sec-/.test(k)));
    await editServer((d) => { d.tables.user_notes = d.tables.user_notes.filter((r) => r.anchor !== "teoriya"); });
    await editLocal((l) => { delete l["bf-pid#teoriya"]; });
    ok("signed in: a synced sec-N note is pushed under its new anchor and the old server row is deleted");

    // a row the server refuses does not block the others, and logout names the real reason
    await editLocal((l) => {
      l["BAD ID#"] = { m: "BAD ID", a: "", body: "hand-edited", at: 1, dirty: true, srv: null };
      l["bf-pid#teoriya"] = { m: "bf-pid", a: "teoriya", body: "good one", at: 2, dirty: true, srv: null, label: "" };
    });
    await p.evaluate(() => window.UAVUserData.syncAll());
    assert.ok((await serverNotes()).some((r) => r.anchor === "teoriya" && r.body === "good one"), "the good row went up");
    await p.goto(`${BASE}/pages/account.html`, { waitUntil: "networkidle" });
    await p.click("[data-acc-logout]");
    await p.waitForFunction(() => /неверной ссылкой/.test(document.querySelector("[data-acc-msg]").textContent));
    await editLocal((l) => { delete l["BAD ID#"]; });
    ok("signed in: one refused row does not block the rest; logout names the reason");

    // the session ends by itself (expired / revoked): unsynced notes stay and go up at the same account's next login
    await p.goto(`${BASE}/${LESSON}`, { waitUntil: "networkidle" });
    await p.waitForFunction(() => window.UAVUserData.pending() === 0, null, { timeout: 8000 });
    await editLocal((l) => { l["bf-pid#praktika"] = { m: "bf-pid", a: "praktika", body: "typed offline", at: 3, dirty: true, srv: null, label: "" }; });
    await p.evaluate(() => window.UAV_BACKEND.client.auth.signOut());     // not our logout: the session just ended
    await p.waitForFunction(() => !window.UAVAccount.state().user);
    let local = await ls(p, NOTES);
    assert.deepStrictEqual(Object.keys(local), ["bf-pid#praktika"], "only the unsynced note is kept");
    await login("nina@example.org", "ninapassword1");
    await p.waitForFunction(() => JSON.parse(localStorage.getItem("fake-supabase-db")).tables.user_notes.some((r) => r.anchor === "praktika" && r.body === "typed offline"), null, { timeout: 8000 });
    // … and another account never gets them; nina's settings do not leak into it either
    await p.check('[data-setting="notesPanel"]');
    await p.waitForFunction(() => { const d = JSON.parse(localStorage.getItem("fake-supabase-db")); return (d.tables.user_settings || []).some((r) => r.data.notesPanel === true); }, null, { timeout: 8000 });
    await editLocal((l) => { l["bf-pid#diagnostika"] = { m: "bf-pid", a: "diagnostika", body: "nina's secret", at: 4, dirty: true, srv: null, label: "" }; });
    await p.evaluate(() => window.UAV_BACKEND.client.auth.signOut());
    await p.waitForFunction(() => !window.UAVAccount.state().user);
    await login("adam@example.org", "adminpassword1");
    await p.waitForFunction(() => !/nina's secret/.test(localStorage.getItem("uav-student:notes:v1") || ""));
    await p.waitForTimeout(2500);
    const d2 = await db(), adam = d2.users.find((u) => u.username === "adam").id;
    assert.ok(!d2.tables.user_notes.some((r) => r.user_id === adam), "adam's account got none of nina's notes");
    assert.ok(!(d2.tables.user_settings || []).some((r) => r.user_id === adam && r.data.notesPanel), "nina's settings did not go into adam's account");
    assert.strictEqual(await p.isChecked('[data-setting="notesPanel"]'), false);
    await logout();
    await login("nina@example.org", "ninapassword1");
    await p.waitForFunction(() => window.UAVUserData.readSettings().notesPanel === true, null, { timeout: 8000 });
    ok("signed in: an expired session keeps unsynced notes for the same account only; settings follow their account");

    // feedback: send, staff sees it and changes the status, the author sees the status
    await p.goto(`${BASE}/${LESSON}`, { waitUntil: "networkidle" });
    await p.locator(".module-body h2 .nb-tools button").nth(2).click();
    await p.fill("dialog.nb-dialog textarea", "short");
    await p.click("dialog.nb-dialog button[type=submit]");
    assert.match(await p.textContent("dialog.nb-dialog .acc-msg"), /хотя бы 10/);
    await p.check('dialog.nb-dialog input[value="unclear"]');
    await p.fill("dialog.nb-dialog textarea", "Where does the 0.65 come from in this section?");
    await p.click("dialog.nb-dialog button[type=submit]");
    await p.waitForSelector("dialog.nb-dialog [role=status]");
    const fb = (await db()).feedback[0];
    assert.deepStrictEqual([fb.module_id, fb.section_key, fb.kind, fb.anchor, fb.page_lang], ["bf-pid", "betaflight", "unclear", "teoriya", "ru"]);
    await p.keyboard.press("Escape");
    await p.goto(`${BASE}/pages/account.html`, { waitUntil: "networkidle" });
    await p.click("[data-acc-logout]");
    await p.waitForSelector('[data-acc="guest"]:not([hidden])');
    await p.fill('[data-form="login"] [name=email]', "adam@example.org");
    await p.fill('[data-form="login"] [name=password]', "adminpassword1");
    await p.click('[data-form="login"] gc-button[type=submit]');
    await p.waitForSelector('[data-acc="user"]:not([hidden])');
    await p.goto(`${BASE}/pages/admin.html`, { waitUntil: "networkidle" });
    await p.waitForSelector("[data-adm-feedback] [data-fb]");
    assert.match(await p.textContent("[data-adm-feedback]"), /0\.65[\s\S]*/);
    assert.ok(/m\/bf-pid\.html#teoriya$/.test(await p.getAttribute("[data-adm-feedback] [data-fb] a", "href")), "link to the exact place");
    await p.selectOption("[data-fb-kind]", "error");
    assert.strictEqual(await p.locator("[data-adm-feedback] [data-fb]").count(), 0);
    await p.selectOption("[data-fb-kind]", "");
    await p.selectOption("[data-fb-set-status]", "done");
    await p.fill("[data-fb-note]", "explained in the next release");
    await p.click("[data-fb-save]");
    await p.waitForFunction(() => /сделано/.test(document.querySelector("[data-adm-feedback] .gc-tag").textContent));
    await noSideScroll(p, 400, "admin page");
    await p.goto(`${BASE}/pages/account.html`, { waitUntil: "networkidle" });
    await p.click("[data-acc-logout]");
    await p.waitForSelector('[data-acc="guest"]:not([hidden])');
    await p.fill('[data-form="login"] [name=email]', "nina@example.org");
    await p.fill('[data-form="login"] [name=password]', "ninapassword1");
    await p.click('[data-form="login"] gc-button[type=submit]');
    await p.waitForSelector("[data-acc-feedback] li");
    assert.match(await p.textContent("[data-acc-feedback]"), /сделано/);
    assert.ok(!/next release/.test(await p.textContent("[data-acc-feedback]")), "the staff note is not shown to the author");
    ok("signed in: feedback reaches the staff with a link to the place; status (not the staff note) reaches the author");
    await ctx.close();
  }

  assert.deepStrictEqual(errors, [], "console errors: " + errors.join(" | "));
  ok("no console errors");
  await browser.close();
  console.log(`1..${n}`);
})().catch((e) => { console.error("not ok - " + e.message); process.exit(1); });
