// Temporary runtime a11y scan (claude-a11y-skill): drives the real flow and
// runs axe-core on each meaningful UI state. Deleted after the audit.
import { chromium } from "playwright";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const axeSource = readFileSync(join(here, "node_modules/axe-core/axe.min.js"), "utf8");
const DEMO_PDF = join(here, "..", "demo", "demo_pay_stub_lowquality.pdf");
const BASE = "http://localhost:5173";

const results = [];

async function runAxe(page, name) {
  await page.evaluate(axeSource);
  const r = await page.evaluate(async () => {
    const res = await window.axe.run(document, {
      runOnly: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"],
    });
    return {
      violations: res.violations.map((v) => ({
        id: v.id,
        impact: v.impact,
        description: v.description,
        helpUrl: v.helpUrl,
        nodes: v.nodes.slice(0, 5).map((n) => ({
          html: n.html.substring(0, 200),
          target: n.target,
          failureSummary: n.failureSummary,
        })),
        nodeCount: v.nodes.length,
      })),
      passes: res.passes.length,
      incomplete: res.incomplete.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length })),
    };
  });
  results.push({ page: name, ...r });
  console.log(`[scan] ${name}: ${r.violations.length} violations, ${r.passes} passes, ${r.incomplete.length} incomplete`);
}

const browser = await chromium.launch();
const page = await browser.newPage();
page.setDefaultTimeout(20000);

// 1. Landing (pre-consent)
await page.goto(BASE + "/");
await page.waitForSelector("#consent");
await runAxe(page, "/ (landing)");

// 2. Consent -> start session -> Profile (empty)
await page.check("#consent");
await page.click("text=Start my session");
await page.waitForURL("**/profile");
await page.waitForSelector("#file-upload");
await runAxe(page, "/profile (empty)");

// 3. Upload degraded demo stub -> populated table + evidence viewer
await page.setInputFiles("#file-upload", DEMO_PDF);
await page.waitForSelector("table", { timeout: 30000 });
await page.waitForSelector("text=abstained");
await page.waitForTimeout(1500); // let the PDF canvas render
await runAxe(page, "/profile (document uploaded)");

// 4. Zoomed evidence state
await page.locator("tbody th button").first().click();
await page.waitForSelector(".pdf-stage.zoomed");
await page.waitForTimeout(1000);
await runAxe(page, "/profile (evidence zoomed)");

// 5. Correct the abstained hourly_rate (confirm-all is blocked until then),
//    then confirm all -> profile complete
await page.click("#correct-hourly_rate");
await page.fill("#edit-hourly_rate", "26.00");
await page.click("text=Save");
await page.waitForSelector("text=corrected by you");
await page.click("text=Confirm all extracted values on this document");
await page.waitForSelector("text=Profile confirmed");
await runAxe(page, "/profile (all confirmed)");

// 6. Understand with calc + Q&A answer
await page.click('nav >> text=2 · Understand');
await page.waitForSelector("text=Deterministic calculation");
await page.click("text=Am I eligible?");
await page.waitForSelector(".qa-answer");
await runAxe(page, "/understand (calc + answer)");

// 7. Prepare with readiness + packet
await page.click('nav >> text=3 · Prepare');
await page.waitForSelector("text=Readiness for human review");
await runAxe(page, "/prepare");

// 8. Delete confirmation alertdialog open (do NOT confirm)
await page.click("text=Delete my session and all data");
await page.waitForSelector('[role="alertdialog"]');
await runAxe(page, "/prepare (delete dialog open)");
await page.keyboard.press("Escape");

// 9. Discover
await page.click('nav >> text=Discover');
await page.waitForSelector("tbody tr");
await runAxe(page, "/discover");

await browser.close();
writeFileSync(join(here, "axe-results.json"), JSON.stringify(results, null, 2));
const total = results.reduce((s, r) => s + r.violations.length, 0);
console.log(`DONE: ${total} total violations across ${results.length} states`);
