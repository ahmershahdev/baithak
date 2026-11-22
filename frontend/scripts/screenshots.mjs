// The README's screenshots, taken from the demo data (manage.py seed_demo) with the dev stack and
// `npm run dev` running. Signs in as the Chai and Code owner with a session made in the backend
// container, so reCAPTCHA (real keys in a local .env) never gets in the way.
//
//   npm run screenshots

import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { chromium } from "@playwright/test";

const WEB = process.env.BAITHAK_WEB ?? "http://localhost:5173";
const OUT = fileURLToPath(new URL("../../docs/screenshots/", import.meta.url));

// Prints the session cookie and where the pictures are, as one line of JSON.
const PYTHON = `
import json
from importlib import import_module
from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
from apps.accounts.models import User
from apps.chat.models import Channel, Message
from apps.issues.models import Issue
user = User.objects.get(email="amna@chai-and-code.example")
session = import_module(settings.SESSION_ENGINE).SessionStore()
session[SESSION_KEY] = str(user.pk)
session[BACKEND_SESSION_KEY] = settings.AUTHENTICATION_BACKENDS[0]
session[HASH_SESSION_KEY] = user.get_session_auth_hash()
session.create()
dev = Channel.objects.get(workspace__slug="chai-and-code", name="dev")
thread = Message.objects.filter(channel=dev, parent=None, reply_count__gte=2, kind="message").order_by("-seq").first()
issue = Issue.objects.filter(workspace__slug="chai-and-code", message__isnull=False).order_by("-number").first()
print(json.dumps({
    "cookie": settings.SESSION_COOKIE_NAME,
    "session": session.session_key,
    "channel": f"/w/chai-and-code/c/{dev.pk}?thread={thread.seq}",
    "issue": f"/w/chai-and-code/projects/{issue.project.key}/issues/{issue.number}",
}))
`;

function backend() {
  const out = execFileSync(
    "docker",
    ["compose", "exec", "-T", "backend", "python", "manage.py", "shell", "-c", PYTHON],
    { encoding: "utf8" },
  );
  return JSON.parse(out.trim().split("\n").at(-1));
}

const SHOTS = (where) => [
  { name: "channel", path: where.channel, scheme: "light" },
  { name: "channel-dark", path: where.channel, scheme: "dark" },
  { name: "board", path: "/w/chai-and-code/projects/BAZ/board", scheme: "light" },
  { name: "issue", path: where.issue, scheme: "light" },
  { name: "search", path: "/w/chai-and-code/search?q=page", scheme: "light" },
];

const where = backend();
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
