// End-to-end check of study groups on the admin page (create, add, filter, CSV per group, remove, delete)
// in Chromium against tests/e2e/fake-supabase.js. The access rules themselves are tested in supabase/tests/test_cohorts.py.
// Run: python3 -m http.server 8765 (repo root) & node tests/e2e/cohorts.e2e.js [http://localhost:8765]
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const assert = require("assert");

const BASE = process.argv[2] || "http://localhost:8765";
const FAKE = fs.readFileSync(path.join(__dirname, "fake-supabase.js"), "utf8");

(async () => {
  const browser = await chromium.launch();
  const errors = [];
  let n = 0; const ok = (name) => console.log(`ok ${++n} - ${name}`);
  const ctx = await browser.newContext({ viewport: { width: 390, height: 860 }, acceptDownloads: true });
  await ctx.addInitScript(FAKE);
  const p = await ctx.newPage();
  p.on("pageerror", (e) => errors.push(e.message));
  p.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  p.on("dialog", (d) => d.accept());

  async function login(email, pw) {
    await p.goto(`${BASE}/pages/account.html`, { waitUntil: "networkidle" });
    if (await p.isVisible('[data-acc="user"]')) { await p.click("[data-acc-logout]"); await p.waitForSelector('[data-acc="guest"]:not([hidden])'); }
    await p.fill('[data-form="login"] [name=email]', email);
    await p.fill('[data-form="login"] [name=password]', pw);
    await p.click('[data-form="login"] gc-button[type=submit]');
    await p.waitForSelector('[data-acc="user"]:not([hidden])');
  }
  const message = () => p.textContent("[data-acc-msg]");
  const names = () => p.$$eval("[data-adm-rows] [data-detail]", (b) => b.map((x) => x.textContent));
  async function createGroup(name) {
    await p.fill("[data-adm-cohort-name]", name);
    await p.click('[data-adm-cohort-form] button[type=submit]');
    await p.waitForFunction(() => /Группа создана|уже есть|от 2 до 100/.test(document.querySelector("[data-acc-msg]").textContent));
  }

  await p.goto(`${BASE}/index.html`, { waitUntil: "networkidle" });
  await p.evaluate(() => window.__fakeSeed([
    { id: "u-adam", email: "adam@example.org", username: "adam", password: "adminpassword1", role: "admin", created_at: "2026-11-01T00:00:00Z" },
    { id: "u-bob", email: "bob@example.org", username: "bob", password: "studentpass1", role: "student", created_at: "2026-11-02T00:00:00Z" },
    { id: "u-cat", email: "cat@example.org", username: "cat", password: "studentpass2", role: "student", created_at: "2026-11-03T00:00:00Z" }
  ], { "u-bob": { quiz: { "f-power": { correct: 8, total: 8 } } } }));

  // 1. admin creates two groups; a duplicate name is refused in plain Russian
  await login("adam@example.org", "adminpassword1");
  await p.goto(`${BASE}/pages/admin.html`, { waitUntil: "networkidle" });
  await p.waitForSelector("[data-adm-rows] tr [data-detail]");
  await createGroup("Весна-2027");
  await createGroup("Осень-2027");
  await p.waitForFunction(() => document.querySelectorAll("[data-adm-cohorts] li strong").length === 2);
  await createGroup("весна-2027");
  assert.match(await message(), /уже есть/);
  ok("admin creates groups; a duplicate name (any case) is refused");

  // 2. add bob to spring, cat to autumn; filter by group
  const spring = await p.$eval("[data-adm-cohort]", (s) => [...s.options].find((o) => o.textContent === "Весна-2027").value);
  await p.selectOption('[data-join-of="u-bob"]', spring);
  await p.waitForFunction(() => /Добавлен в группу/.test(document.querySelector("[data-acc-msg]").textContent));
  const autumn = await p.$eval("[data-adm-cohort]", (s) => [...s.options].find((o) => o.textContent === "Осень-2027").value);
  await p.selectOption('[data-join-of="u-cat"]', autumn);
  await p.waitForFunction(() => /cat[\s\S]*Осень-2027 ×/.test(document.querySelector("[data-adm-rows]").textContent));
  await p.selectOption("[data-adm-cohort]", spring);
  assert.deepStrictEqual(await names(), ["bob"]);
  await p.selectOption("[data-adm-cohort]", "-");
  assert.deepStrictEqual(await names(), ["adam"]);
  ok("students join groups from the table; the filter shows one group or the ungrouped");

  // 2b. bob sees his own group name on his account page, nothing about the others
  await login("bob@example.org", "studentpass1");
  await p.waitForSelector("[data-acc-groups]:not([hidden])");
  assert.strictEqual(await p.textContent("[data-acc-group-names]"), "Весна-2027");
  await login("adam@example.org", "adminpassword1");
  await p.goto(`${BASE}/pages/admin.html`, { waitUntil: "networkidle" });
  await p.waitForSelector("[data-adm-rows] tr [data-detail]");
  ok("a student sees only the names of their own groups on the account page");

  // 3. CSV follows the filter and carries the groups column
  await p.selectOption("[data-adm-cohort]", spring);
  const [dl] = await Promise.all([p.waitForEvent("download"), p.click("[data-adm-csv]")]);
  assert.match(dl.suggestedFilename(), /^uav-students-vesna-2027-\d{4}-\d{2}-\d{2}\.csv$/);
  const text = fs.readFileSync(await dl.path(), "utf8").replace(/^﻿/, "").trim().split("\n");
  assert.strictEqual(text[0], "username,email,role,groups,mastered,total,score,updated_at");
  assert.strictEqual(text.length, 2, text.join(" | "));
  assert.match(text[1], /^bob,bob@example\.org,student,Весна-2027,/);
  ok("CSV per group: only the group's students, with a groups column");

  // 4. filter survives a reload of the data; remove from the group; delete a group
  await p.click("[data-adm-reload]");
  await p.waitForFunction(() => document.querySelectorAll("[data-adm-rows] [data-detail]").length === 1);
  await p.selectOption("[data-adm-cohort]", "");
  await p.click('[data-unjoin][data-user="u-bob"]');
  await p.waitForFunction(() => /Убран из группы/.test(document.querySelector("[data-acc-msg]").textContent));
  assert.ok(!/Весна-2027 ×/.test(await p.textContent("[data-adm-rows]")));
  await p.click(`[data-cohort-del="${autumn}"]`);
  await p.waitForFunction(() => /Группа удалена/.test(document.querySelector("[data-acc-msg]").textContent));
  assert.ok(!/Осень-2027/.test(await p.textContent("[data-adm-cohorts]")));
  assert.ok(/cat/.test(await p.textContent("[data-adm-rows]")), "deleting a group keeps its students");
  ok("remove a student from a group; delete a group, its students stay");

  const sw = await p.evaluate(() => document.documentElement.scrollWidth);
  assert.ok(sw <= 390, "admin page scrollWidth " + sw);
  assert.deepStrictEqual(errors, [], "console errors: " + errors.join(" | "));
  ok("no console errors, no horizontal scroll at 390 px");
  await browser.close();
  console.log(`1..${n}`);
})().catch((e) => { console.error("not ok -", e.message); process.exit(1); });
