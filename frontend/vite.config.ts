import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import type { Plugin } from "vite";
import { defineConfig } from "vitest/config";

// The built app has no inline scripts, so script-src lists sources instead of a per-request
// nonce: our own files and Google's reCAPTCHA. Inline style attributes stay allowed because
// the reCAPTCHA widget sets them. frame-ancestors can't be set from a meta tag; the server in
// front of the app sends it as a header (docs/architecture.md).
const CSP = [
  "default-src 'self'",
  "script-src 'self' https://www.google.com/recaptcha/ https://www.gstatic.com/recaptcha/",
  "frame-src https://www.google.com/recaptcha/ https://recaptcha.google.com/recaptcha/",
  "connect-src 'self' https://www.google.com/recaptcha/",
  "img-src 'self' data:",
  "font-src 'self'",
  "style-src 'self' 'unsafe-inline'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

// Only for the production build: the dev server needs inline scripts for hot reload.
function contentSecurityPolicy(): Plugin {
  return {
    name: "baithak-csp",
    apply: "build",
    transformIndexHtml: () => [
      {
        tag: "meta",
        attrs: { "http-equiv": "Content-Security-Policy", content: CSP },
        injectTo: "head-prepend",
      },
    ],
  };
}

const backend = process.env.BAITHAK_BACKEND_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react(), tailwindcss(), contentSecurityPolicy()],
  server: {
    port: 5173,
    // The browser only ever talks to Vite in development, so session cookies and CSRF stay
    // same-origin, as they will be behind the production proxy.
    proxy: {
      "/api": backend,
      "/health": backend,
      "/admin": backend,
      "/static": backend,
      "/ws": { target: backend, ws: true },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
});
