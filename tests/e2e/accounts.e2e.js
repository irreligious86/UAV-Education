// End-to-end check of the account UI in Chromium against tests/e2e/fake-supabase.js.
// Run: python3 -m http.server 8765 (repo root) & node tests/e2e/accounts.e2e.js [http://localhost:8765]
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const assert = require("assert");

const BASE = process.argv[2] || "http://localhost:8765";
const FAKE = fs.readFileSync(path.join(__dirname, "fake-supabase.js"), "utf8");
const LOCAL = "uav-student:progress:v1";

(async () => {
  const browser = await chromium.launch();
  const errors = [];
  const watch = (p) => { p.on("pageerror", (e) => errors.push(e.message)); p.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); }); };
  let n = 0; const ok = (name) => console.log(`ok ${++n} - ${name}`);

  // 1. flag off: nothing changes
  {
    const ctx = await browser.newContext(); const p = await ctx.newPage(); watch(p);
    await p.goto(`${BASE}/pages/account.html`, { waitUntil: "networkidle" });
    assert.strictEqual(await p.isVisible('[data-acc="off"]'), true);
    assert.strictEqual(await p.$("#nav-account"), null);
    assert.strictEqual(await p.evaluate(() => window.UAVAccount.enabled), false);
    await p.goto(`${BASE}/index.html`, { waitUntil: "networkidle" });
    assert.strictEqual(await p.evaluate(() => [...document.scripts].some((s) => /vendor\/supabase/.test(s.src))), false);
    await ctx.close(); ok("flag off: account page explains, no nav link, supabase not loaded");
  }

  const ctx = await browser.newContext({ viewport: { width: 390, height: 860 } });
  await ctx.addInitScript(FAKE);
  const p = await ctx.newPage(); watch(p);
  await p.goto(`${BASE}/index.html`, { waitUntil: "networkidle" });
  await p.evaluate(() => window.__fakeSeed([
    { id: "u-boss", email: "boss@example.org", username: "boss", password: "superpassword1", role: "superadmin", created_at: "2026-11-01T00:00:00Z" },
    { id: "u-adam", email: "adam@example.org", username: "adam", password: "adminpassword1", role: "admin", created_at: "2026-11-01T00:00:00Z" },
    { id: "u-bob", email: "bob@example.org", username: "bob", password: "studentpass1", role: "student", created_at: "2026-11-02T00:00:00Z" }
  ], { "u-bob": { done: ["f-physics"], quiz: { "f-physics": { correct: 8, total: 8, ts: 1 } }, checks: ["f-physics:lab:0", "f-physics:lab:1", "f-physics:lab:2", "f-physics:lab:3"], tasks: { "f-physics": { t1: true, t2: true } } } }));
  // anonymous study before registering
  await p.evaluate((k) => localStorage.setItem(k, JSON.stringify({ done: ["f-mechanics"], quiz: { "f-mechanics": { correct: 7, total: 8, ts: 2 } } })), LOCAL);
  assert.ok(await p.isVisible("#nav-account"));
  assert.strictEqual(await p.textContent("#nav-account"), "Войти");
  ok("flag on: nav shows the login link");

  // 2. registration merges anonymous progress into the account
  await p.goto(`${BASE}/pages/account.html`, { waitUntil: "networkidle" });
  await p.click('[data-tab="register"]');
  const reg = '[data-form="register"]';
  await p.fill(`${reg} [name=email]`, "alice@example.org");
  await p.fill(`${reg} [name=username]`, "alice");
  await p.fill(`${reg} [name=password]`, "short");
  await p.press(`${reg} [name=password]`, "Enter");
  assert.strictEqual(await p.isVisible('[data-acc="user"]'), false, "short password must not register");
  await p.fill(`${reg} [name=password]`, "alicepassword1");
  await p.click(`${reg} gc-button[type=submit]`);
  await p.waitForSelector('[data-acc="user"]:not([hidden])');
  await p.waitForFunction(() => document.querySelector("[data-acc-sync]").textContent === "сохранено");
  assert.strictEqual(await p.textContent("[data-acc-username]"), "alice");
  assert.strictEqual(await p.textContent("#nav-account"), "👤 alice");
  const server = await p.evaluate(() => { const db = JSON.parse(localStorage.getItem("fake-supabase-db")); const u = db.users.find((x) => x.username === "alice"); return db.progress[u.id].data; });
  assert.deepStrictEqual(server.done, ["f-mechanics"]);
  assert.strictEqual(server.quiz["f-mechanics"].correct, 7);
  ok("register: logged in, anonymous progress pushed to the account");

  // 3. later local writes are pushed (debounced)
  await p.evaluate(() => window.UAVProgress.setQuiz("f-power", { correct: 6, total: 8, ts: Date.now() }));
  await p.waitForFunction(() => { const db = JSON.parse(localStorage.getItem("fake-supabase-db")); const u = db.users.find((x) => x.username === "alice"); return !!db.progress[u.id].data.quiz["f-power"]; }, null, { timeout: 5000 });
  ok("progress writes reach the server");

  // 4. duplicate username and wrong password give readable errors
  await p.click("[data-acc-logout]");
  await p.waitForSelector('[data-acc="guest"]:not([hidden])');
  assert.strictEqual(await p.evaluate((k) => localStorage.getItem(k), LOCAL), null, "logout clears the local copy");
  await p.click('[data-tab="login"]');
  await p.fill('[data-form="login"] [name=email]', "alice@example.org");
  await p.fill('[data-form="login"] [name=password]', "wrongpassword");
  await p.click('[data-form="login"] gc-button[type=submit]');
  await p.waitForFunction(() => /Неверная почта или пароль/.test(document.querySelector("[data-acc-msg]").textContent));
  await p.click('[data-tab="register"]');
  await p.fill(`${reg} [name=email]`, "other@example.org");
  await p.fill(`${reg} [name=username]`, "alice");
  await p.fill(`${reg} [name=password]`, "otherpassword1");
  await p.click(`${reg} gc-button[type=submit]`);
  await p.waitForFunction(() => /занято/.test(document.querySelector("[data-acc-msg]").textContent));
  ok("logout clears local copy; wrong password and taken username explained");

  // 5. login on a "new device" restores progress from the server
  await p.click('[data-tab="login"]');
  await p.fill('[data-form="login"] [name=email]', "alice@example.org");
  await p.fill('[data-form="login"] [name=password]', "alicepassword1");
  await p.click('[data-form="login"] gc-button[type=submit]');
  await p.waitForSelector('[data-acc="user"]:not([hidden])');
  await p.waitForFunction((k) => { const d = JSON.parse(localStorage.getItem(k) || "{}"); return d.quiz && d.quiz["f-power"]; }, LOCAL);
  ok("login restores progress from the server");

  // 6. a student does not get the admin page
  await p.goto(`${BASE}/pages/admin.html`, { waitUntil: "networkidle" });
  assert.strictEqual(await p.isVisible('[data-adm="on"]'), false);
  assert.strictEqual(await p.$("#nav-admin"), null);
  await p.goto(`${BASE}/pages/account.html`, { waitUntil: "networkidle" });
  await p.click("[data-acc-logout]");
  await p.waitForSelector('[data-acc="guest"]:not([hidden])');
  ok("student: no admin page, no admin link");

  // 6b. another account's progress left in the browser is wiped, not merged into the next account (review M3)
  await p.evaluate((k) => { localStorage.setItem(k, JSON.stringify({ done: ["leaked-module"] })); localStorage.setItem("uav-student:owner", "u-someone-else"); }, LOCAL);
  await p.fill('[data-form="login"] [name=email]', "bob@example.org");
  await p.fill('[data-form="login"] [name=password]', "studentpass1");
  await p.click('[data-form="login"] gc-button[type=submit]');
  await p.waitForSelector('[data-acc="user"]:not([hidden])');
  await p.waitForFunction(() => document.querySelector("[data-acc-sync]").textContent === "сохранено");
  const bobServer = await p.evaluate(() => JSON.parse(localStorage.getItem("fake-supabase-db")).progress["u-bob"].data);
  assert.ok(!(bobServer.done || []).includes("leaked-module"), "foreign local progress must not reach bob");
  assert.ok((bobServer.done || []).includes("f-physics"));
  await p.click("[data-acc-logout]");
  await p.waitForSelector('[data-acc="guest"]:not([hidden])');
  ok("shared browser: another account's leftovers are wiped, not merged");

  // 7. admin sees grades, cannot change roles
  await p.fill('[data-form="login"] [name=email]', "adam@example.org");
  await p.fill('[data-form="login"] [name=password]', "adminpassword1");
  await p.click('[data-form="login"] gc-button[type=submit]');
  await p.waitForSelector("#nav-admin");
  await p.goto(`${BASE}/pages/admin.html`, { waitUntil: "networkidle" });
  await p.waitForSelector("[data-adm-rows] tr td");
  const rows = await p.$$eval("[data-adm-rows] tr", (trs) => trs.map((t) => t.innerText));
  assert.strictEqual(rows.length, 4);
  const bob = rows.find((r) => /bob/.test(r));
  assert.ok(/1 \/ 117/.test(bob), "bob mastered f-physics: " + bob);
  assert.strictEqual(await p.$("[data-role-of]"), null, "admin gets no role selectors");
  await p.click('[data-detail="u-bob"]');
  await p.waitForSelector("[data-adm-detail]:not([hidden]) table");
  assert.ok(/Как летает мультиротор/.test(await p.textContent("[data-adm-detail]")));
  await p.fill("[data-adm-filter]", "ali");
  assert.strictEqual(await p.$$eval("[data-adm-rows] tr", (t) => t.length), 1);
  ok("admin: grades of everyone, per-student detail, filter; no role control");

  // 8. superadmin changes a role; audit shows it; own row and superadmin row have no selector
  await p.goto(`${BASE}/pages/account.html`, { waitUntil: "networkidle" });
  await p.click("[data-acc-logout]");
  await p.waitForSelector('[data-acc="guest"]:not([hidden])');
  await p.fill('[data-form="login"] [name=email]', "boss@example.org");
  await p.fill('[data-form="login"] [name=password]', "superpassword1");
  await p.click('[data-form="login"] gc-button[type=submit]');
  await p.waitForSelector("#nav-admin");
  await p.goto(`${BASE}/pages/admin.html`, { waitUntil: "networkidle" });
  await p.waitForSelector("[data-role-of]");
  assert.strictEqual(await p.$('[data-role-of="u-boss"]'), null);
  assert.strictEqual(await p.$$eval("[data-role-of]", (s) => s.length), 3);
  await p.selectOption('[data-role-of="u-bob"]', "admin");
  await p.waitForFunction(() => /Роль изменена/.test(document.querySelector("[data-acc-msg]").textContent));
  await p.waitForFunction(() => /bob/.test(document.querySelector("[data-adm-audit]").textContent));
  const role = await p.evaluate(() => JSON.parse(localStorage.getItem("fake-supabase-db")).users.find((u) => u.username === "bob").role);
  assert.strictEqual(role, "admin");
  ok("superadmin: role change goes through set_role and lands in the audit log");

  // 9. phone width: no horizontal overflow
  for (const page of ["admin", "account"]) {
    await p.goto(`${BASE}/pages/${page}.html`, { waitUntil: "networkidle" });
    await p.waitForTimeout(300);
    const sw = await p.evaluate(() => document.documentElement.scrollWidth);
    assert.ok(sw <= 390, `${page}: scrollWidth ${sw}`);
    await p.screenshot({ path: path.join(require("os").tmpdir(), `acc-${page}.png`), fullPage: true });
  }
  ok("phone width: no horizontal scroll on account and admin pages");

  assert.deepStrictEqual(errors, [], "console errors: " + errors.join(" | "));
  ok("no console errors");
  await browser.close();
  console.log(`1..${n}`);
})().catch((e) => { console.error("not ok -", e.message); process.exit(1); });
