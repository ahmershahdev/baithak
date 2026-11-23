import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState, type RefObject } from "react";

import { api } from "./api/client";

interface Grecaptcha {
  ready(callback: () => void): void;
  execute(siteKey: string, options: { action: string }): Promise<string>;
  render(
    container: HTMLElement,
    options: {
      sitekey: string;
      theme: "light" | "dark";
      callback: (token: string) => void;
      "expired-callback": () => void;
      "error-callback": () => void;
    },
  ): number;
  reset(widget?: number): void;
}

declare global {
  interface Window {
    grecaptcha?: Grecaptcha;
  }
}

const SCRIPT_ID = "recaptcha-script";

function loadScript(v3Key: string): Promise<Grecaptcha> {
  return new Promise((resolve, reject) => {
    const ready = () => {
      if (window.grecaptcha)
        window.grecaptcha.ready(() => {
          resolve(window.grecaptcha as Grecaptcha);
        });
    };
    if (window.grecaptcha) {
      ready();
      return;
    }
    let script = document.getElementById(SCRIPT_ID) as HTMLScriptElement | null;
    if (!script) {
      script = document.createElement("script");
      script.id = SCRIPT_ID;
      script.src = `https://www.google.com/recaptcha/api.js?render=${encodeURIComponent(v3Key || "explicit")}`;
      script.async = true;
      document.head.append(script);
    }
    script.addEventListener("load", ready);
    script.addEventListener("error", () => {
      reject(new Error("reCAPTCHA did not load"));
    });
  });
}

function pageTheme(): "light" | "dark" {
  const chosen = document.documentElement.dataset.theme;
  if (chosen === "light" || chosen === "dark") return chosen;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function useAuthConfig() {
  return useQuery({
    queryKey: ["auth-config"],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/auth/config/");
      return data ?? { recaptcha_v3_site_key: "", recaptcha_v2_site_key: "", providers: [] };
    },
    staleTime: Infinity,
  });
}

export interface CaptchaFields {
  captcha?: string;
  captcha_v2?: string;
}

/**
 * reCAPTCHA for one form. `tokens()` gives the fields to send with the form; when the API
 * answers `{"captcha": "v2"}`, call `challenge()` and the checkbox appears in `box`.
 */
export function useCaptcha(action: string, box: RefObject<HTMLDivElement | null>) {
  const config = useAuthConfig();
  const widget = useRef<number | null>(null);
  const [v2Token, setV2Token] = useState<string | null>(null);
  const [challenged, setChallenged] = useState(false);
  const [failed, setFailed] = useState(false);

  const v3Key = config.data?.recaptcha_v3_site_key ?? "";
  const v2Key = config.data?.recaptcha_v2_site_key ?? "";

  // The checkbox is drawn only after React has shown its container: reCAPTCHA measures the
  // box when it renders, and inside a display:none parent it comes out blank or squashed.
  useEffect(() => {
    if (!v2Key || widget.current !== null) return;
    let cancelled = false;
    loadScript(v3Key)
      .then((grecaptcha) => {
        if (cancelled || !box.current || widget.current !== null) return;
        widget.current = grecaptcha.render(box.current, {
          sitekey: v2Key,
          theme: pageTheme(),
          callback: (token) => {
            setV2Token(token);
          },
          "expired-callback": () => {
            setV2Token(null);
          },
          "error-callback": () => {
            setFailed(true);
          },
        });
      })
      .catch(() => {
        setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [box, v2Key, v3Key]);

  const tokens = useCallback(async (): Promise<CaptchaFields> => {
    if (v2Token) {
      // Google accepts a checkbox token once. Clear it and untick the box now, so a retry
      // after a wrong password asks for a fresh tick instead of failing the person check.
      setV2Token(null);
      if (widget.current !== null) window.grecaptcha?.reset(widget.current);
      return { captcha_v2: v2Token };
    }
    if (!v3Key) return {};
    try {
      const grecaptcha = await loadScript(v3Key);
      return { captcha: await grecaptcha.execute(v3Key, { action }) };
    } catch {
      // The API decides what a missing token means; it asks for the checkbox when it can.
      return {};
    }
  }, [action, v2Token, v3Key]);

  const challenge = useCallback(() => {
    setV2Token(null);
    setFailed(false);
    if (widget.current !== null) window.grecaptcha?.reset(widget.current);
    setChallenged(true);
  }, []);

  return {
    tokens,
    challenge,
    challenged,
    shown: Boolean(v2Key),
    solved: v2Token !== null,
    failed,
    enabled: Boolean(v3Key || v2Key),
  };
}
