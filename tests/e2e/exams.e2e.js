// End-to-end check of exams (admin uploads a bank, student takes it, admin sees the result)
// in Chromium against tests/e2e/fake-supabase.js. The access rules themselves are tested in supabase/tests.
// Run: python3 -m http.server 8765 (repo root) & node tests/e2e/exams.e2e.js [http://localhost:8765]
const { chromium } = require("playwright");
const fs = require("fs");
const os = require("os");
const path = require("path");
const assert = require("assert");

const BASE = process.argv[2] || "http://localhost:8765";
const FAKE = fs.readFileSync(path.join(__dirname, "fake-supabase.js"), "utf8");

(async () => {
  const browser = await chromium.launch();
  const errors = [];
  let n = 0; const ok = (name) => console.log(`ok ${++n} - ${name}`);
  const ctx = await browser.newContext({ viewport: { width: 390, height: 860 } });
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

  await p.goto(`${BASE}/index.html`, { waitUntil: "networkidle" });
  await p.evaluate(() => window.__fakeSeed([
    { id: "u-adam", email: "adam@example.org", username: "adam", password: "adminpassword1", role: "admin", created_at: "2026-11-01T00:00:00Z" },
    { id: "u-bob", email: "bob@example.org", username: "bob", password: "studentpass1", role: "student", created_at: "2026-11-02T00:00:00Z" }
  ]));

  // 1. admin uploads a bank and publishes it
  const bank = { title: "Итоговый: питание", pass_pct: 60, questions_per_attempt: 3, time_limit_min: 10, attempts_allowed: 1, show_review: true,
    questions: [
      { q: "Напряжение хранения LiPo на банку?", options: ["4.20 В", "3.80–3.85 В", "3.30 В"], answer: 1, explain: "Storage 3.80–3.85 В." },
      { q: "Сколько дБ даёт удвоение мощности?", options: ["3 дБ", "6 дБ", "10 дБ"], answer: 0, explain: "10·log10(2) ≈ 3 дБ." },
      { q: "Порог посадки LiPo под нагрузкой?", options: ["3.5 В", "2.5 В", "4.0 В"], answer: 0, explain: "≈ 3.5 В на банку." }
    ] };
  const file = path.join(os.tmpdir(), "bank-power.json");
  fs.writeFileSync(file, JSON.stringify(bank));
  await login("adam@example.org", "adminpassword1");
  await p.goto(`${BASE}/pages/admin.html`, { waitUntil: "networkidle" });
  await p.waitForSelector("[data-adm-exams] li");
  await p.setInputFiles("[data-adm-exam-file]", file);
  await p.waitForFunction(() => /загружен черновиком/.test(document.querySelector("[data-acc-msg]").textContent));
  await p.click("[data-exam-pub]");
  await p.waitForFunction(() => /опубликован/.test(document.querySelector("[data-adm-exams]").textContent));
  ok("admin uploads a JSON bank as a draft and publishes it");

  // 2. student takes the exam: questions arrive without answers
  await login("bob@example.org", "studentpass1");
  await p.waitForSelector("#nav-exams");
  await p.goto(`${BASE}/pages/exam.html`, { waitUntil: "networkidle" });
  await p.waitForSelector("[data-start]");
  const before = await p.evaluate(() => document.body.innerHTML);
  assert.ok(!/Storage 3\.80|10·log10/.test(before), "explanations must not be on the page before submitting");
  await p.click("[data-start]");
  await p.waitForSelector('[data-ex="run"]:not([hidden]) fieldset');
  assert.strictEqual(await p.$$eval("[data-ex-questions] fieldset", (f) => f.length), 3);
  assert.ok(!/Storage 3\.80|10·log10/.test(await p.evaluate(() => document.body.innerHTML)));
  ok("student starts: 3 questions, no answers or explanations in the page");

  // answer two right, one wrong (the test reads the fake database; the page cannot)
  const key = await p.evaluate(() => { const db = JSON.parse(localStorage.getItem("fake-supabase-db")); const m = {}; db.exam_questions.forEach((q) => { m[q.id] = q.answer; }); return m; });
  const ids = await p.$$eval("[data-ex-questions] fieldset", (fs) => fs.map((f) => f.querySelector("input").getAttribute("data-q")));
  for (let i = 0; i < ids.length; i++) {
    const pick = i === 0 ? (key[ids[i]] + 1) % 3 : key[ids[i]];
    await p.check(`[data-ex-questions] input[data-q="${ids[i]}"][value="${pick}"]`);
  }
  // reload mid-exam: the attempt and the picks survive
  await p.reload({ waitUntil: "networkidle" });
  await p.waitForSelector("[data-start]");
  await p.click("[data-start]");
  await p.waitForSelector('[data-ex="run"]:not([hidden]) fieldset');
  assert.strictEqual(await p.$$eval("[data-ex-questions] input:checked", (x) => x.length), 3, "picks restored after reload");
  ok("reload mid-exam resumes the same attempt with saved picks");

  await p.click("[data-ex-submit]");
  await p.waitForSelector('[data-ex="result"]:not([hidden])');
  const score = await p.textContent("[data-ex-score]");
  assert.ok(/Сдан/.test(score) && /2 из 3/.test(score) && /67 %/.test(score), score);
  assert.strictEqual(await p.$$eval("[data-ex-review] li", (l) => l.length), 3);
  ok("submit: graded 2 of 3 (67 %), passed at 60 %, review shown");

  await p.click("[data-ex-back]");
  await p.waitForSelector("[data-ex-list] .exam-card");
  assert.strictEqual(await p.$("[data-start]"), null, "no start button after the only attempt");
  assert.ok(/сдан · 67 %/.test(await p.textContent("[data-ex-list]")));
  ok("list shows the result and no further attempt");

  const sw = await p.evaluate(() => document.documentElement.scrollWidth);
  assert.ok(sw <= 390, "exam page scrollWidth " + sw);

  // 3. admin sees the result; bob's logout wiped any exam picks left in this browser (review L5)
  await p.evaluate(() => localStorage.setItem("uav-student:exam-draft:left-over", JSON.stringify({ attempt: "x", picks: { 1: 2 } })));
  await login("adam@example.org", "adminpassword1");
  assert.deepStrictEqual(await p.evaluate(() => Object.keys(localStorage).filter((k) => k.startsWith("uav-student:exam-draft:"))), [],
    "exam drafts must not survive a logout");
  await p.goto(`${BASE}/pages/admin.html`, { waitUntil: "networkidle" });
  await p.waitForFunction(() => /bob/.test(document.querySelector("[data-adm-exam-results]").textContent));
  const row = await p.textContent("[data-adm-exam-results]");
  assert.ok(/2 \/ 3 · 67 %/.test(row) && /да/.test(row), row);
  assert.ok(!/удалить/.test(await p.textContent("[data-adm-exams]")), "an exam with attempts cannot be deleted");
  ok("admin sees the graded attempt; the exam with attempts has no delete button");

  assert.deepStrictEqual(errors, [], "console errors: " + errors.join(" | "));
  ok("no console errors, no horizontal scroll at 390 px");
  await browser.close();
  console.log(`1..${n}`);
})().catch((e) => { console.error("not ok -", e.message); process.exit(1); });
