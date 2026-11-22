// The README's screenshots, taken from the demo data (manage.py seed_demo) with the dev stack and
// `npm run dev` running. Signs in as the Chai and Code owner with a session made in the backend
// container (scripts/screenshot-session.py), so reCAPTCHA (real keys in a local .env) never gets
// in the way.
//
//   npm run screenshots

import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { chromium } from "@playwright/test";

const WEB = process.env.BAITHAK_WEB ?? "http://localhost:5173";
const OUT = fileURLToPath(new URL("../../docs/screenshots/", import.meta.url));

// What scripts/screenshot-session.py printed in the backend container, piped in by
// `npm run screenshots`: the last line of stdin.
async function backend() {
  let input = "";
  for await (const chunk of process.stdin) input += chunk;
  return JSON.parse(input.trim().split("\n").at(-1));
}

const SHOTS = (where) => [
  { name: "channel", path: where.channel, scheme: "light" },
  { name: "channel-dark", path: where.channel, scheme: "dark" },
  { name: "board", path: "/w/chai-and-code/projects/BAZ/board", scheme: "light" },
  { name: "issue", path: where.issue, scheme: "light" },
  { name: "search", path: "/w/chai-and-code/search?q=page", scheme: "light" },
];

const where = await backend();
mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch();
try {
  for (const shot of SHOTS(where)) {
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      colorScheme: shot.scheme,
    });
    await context.addCookies([
      { name: where.cookie, value: where.session, url: WEB, httpOnly: true, sameSite: "Lax" },
    ]);
    const page = await context.newPage();
    await page.goto(WEB + shot.path, { waitUntil: "networkidle" });
    await page.evaluate("document.fonts.ready");
    // Let entrance animations finish so nothing is caught half faded in.
    await page.waitForTimeout(800);
    await page.screenshot({ path: `${OUT}${shot.name}.png` });
    console.log(`docs/screenshots/${shot.name}.png`);
    await context.close();
  }
} finally {
  await browser.close();
}
