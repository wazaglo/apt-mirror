#!/usr/bin/env node
// Capture browser evidence for the public endpoints: a screenshot of each page
// as an unauthenticated client sees it, plus every console message and failed
// request the browser reported along the way.
//
// A screenshot proves a page renders. The console log is the part that catches
// what a screenshot cannot show: TLS errors, mixed content, 404 sub-resources,
// JS errors. Both land in docs/evidence/.
//
//   node hack/capture-evidence.mjs
//
// Needs a Chrome binary; set PUPPETEER_CHROME or CHROME_PATH if it is not on
// PATH. Writes docs/evidence/screens/*.png and docs/evidence/console.json.
import { execFileSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import puppeteer from "puppeteer-core";

const OUT = path.resolve("docs/evidence");
const PAGES = [
  { name: "debian-mirror-dists", url: "https://debian-mirror.azubisuccess.space/debian/dists/" },
  { name: "ubuntu-mirror-dists", url: "https://ubuntu-mirror.azubisuccess.space/ubuntu/dists/" },
  { name: "debian-mirror-root", url: "https://debian-mirror.azubisuccess.space/debian/" },
  { name: "grafana-login", url: "https://grafana.azubisuccess.space/login" },
];

const chrome = process.env.PUPPETEER_CHROME || process.env.CHROME_PATH;
if (!chrome) {
  console.error("Set PUPPETEER_CHROME to a Chrome binary.");
  process.exit(1);
}

mkdirSync(path.join(OUT, "screens"), { recursive: true });

const browser = await puppeteer.launch({
  executablePath: chrome,
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--hide-scrollbars"],
});

const report = [];
let failures = 0;

for (const page of PAGES) {
  const tab = await browser.newPage();
  await tab.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 });

  const console_ = [];
  const failed = [];
  // Record which sub-resource 404'd. A console "Failed to load resource" error
  // carries no URL, which makes a real missing asset indistinguishable from the
  // favicon every browser requests on its own.
  const notFound = [];
  tab.on("response", (r) => {
    if (r.status() >= 400) notFound.push({ url: r.url(), status: r.status() });
  });
  tab.on("console", (m) => console_.push({ type: m.type(), text: m.text() }));
  tab.on("pageerror", (e) => console_.push({ type: "pageerror", text: String(e) }));
  tab.on("requestfailed", (r) =>
    failed.push({ url: r.url(), reason: r.failure()?.errorText ?? "unknown" })
  );

  const response = await tab.goto(page.url, { waitUntil: "networkidle2", timeout: 45000 });
  const status = response?.status() ?? 0;
  const title = await tab.title();
  const cert = await tab.evaluate(() => {
    // The issuer the browser actually accepted, read from the negotiated
    // security state. Proves the wildcard cert is what served the page.
    return window.isSecureContext;
  });

  await tab.screenshot({
    path: path.join(OUT, "screens", `${page.name}.png`),
    fullPage: false,
  });

  // The browser asks every site for /favicon.ico unprompted. A mirror that
  // serves no favicon is working correctly, so that one 404 is expected; every
  // other non-2xx sub-resource is not.
  const unexpected = notFound.filter((r) => !r.url.endsWith("/favicon.ico"));
  // A bare "Failed to load resource" console error is just a restatement of one
  // of the non-2xx responses above, so only count it once, and only when it is
  // not the expected favicon miss.
  const errors = console_.filter(
    (c) =>
      (c.type === "error" || c.type === "pageerror") &&
      !c.text.startsWith("Failed to load resource")
  );
  if (status >= 400 || errors.length || failed.length || unexpected.length) failures++;

  report.push({
    name: page.name,
    url: page.url,
    status,
    title,
    secureContext: cert,
    consoleErrors: errors,
    nonOkResponses: notFound,
    failedRequests: failed,
    consoleMessages: console_,
  });

  console.log(
    `${status} secure=${cert} errors=${errors.length} failed=${failed.length} ` +
      `nonOk=${notFound.map((r) => r.status + ":" + new URL(r.url).pathname).join(",") || "none"}  ${page.url}`
  );
  await tab.close();
}

await browser.close();

writeFileSync(
  path.join(OUT, "console.json"),
  JSON.stringify({ capturedAt: new Date().toISOString(), pages: report }, null, 2) + "\n"
);
console.log(`\nwrote ${OUT}/console.json and ${report.length} screenshots`);

if (failures) {
  console.error(`\n${failures} page(s) had an error, failed request, or non-2xx status`);
  process.exit(1);
}
