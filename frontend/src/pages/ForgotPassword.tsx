import { useMutation } from "@tanstack/react-query";
import { useRef, useState, type SubmitEvent } from "react";
import { Link } from "react-router";

import { api, readErrors, type ApiErrors } from "../api/client";
import { useCaptcha } from "../captcha";
import { CaptchaBox, CaptchaNotice } from "../components/CaptchaBox";
import {
  AuthLayout,
  Button,
  ErrorMessage,
  Field,
  Honeypot,
  Notice,
  TextLink,
} from "../components/ui";
import { honeypot, textField } from "../forms";

export function ForgotPassword() {
  const captchaBox = useRef<HTMLDivElement>(null);
  const captcha = useCaptcha("password_reset", captchaBox);
  const [errors, setErrors] = useState<ApiErrors>({ fields: {} });
  const [sentTo, setSentTo] = useState<string | null>(null);

  const request = useMutation({
    mutationFn: async (body: { email: string; website: string }) =>
      api.POST("/api/v1/auth/password-reset/", {
        body: { ...body, ...(await captcha.tokens()) },
      }),
    onSuccess: ({ response, error }, body) => {
      if (response.status === 202) {
        setSentTo(body.email);
        return;
      }
      const problems = readErrors(error);
      setErrors(problems);
      if (problems.captcha) captcha.challenge();
    },
    onError: () => {
      setErrors({ detail: "Could not reach Baithak. Try again.", fields: {} });
    },
  });

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setErrors({ fields: {} });
    request.mutate({ email: textField(form, "email"), ...honeypot(form) });
  }

  return (
    <AuthLayout
      title="Forgot your password?"
      intro="It happens. We will email you a code to choose a new one."
    >
      {sentTo !== null ? (
        <div className="flex flex-col gap-4">
          <Notice>
            If <strong>{sentTo}</strong> has an account, a 6-digit code is on its way. It expires in
            10 minutes.
          </Notice>
          <Link
            to="/reset-password"
            state={{ email: sentTo }}
            className="btn-lamp inline-flex h-12 items-center justify-center rounded-xl bg-accent px-5 font-semibold text-on-accent hover:bg-accent-hover focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:outline-none"
          >
            Enter the code
          </Link>
        </div>
      ) : (
        <form onSubmit={submit} className="relative flex flex-col gap-5" noValidate>
          {errors.detail && <ErrorMessage>{errors.detail}</ErrorMessage>}
          <Field
            label="Email"
            name="email"
            type="email"
            inputMode="email"
            autoComplete="email"
            placeholder="you@company.com"
            required
            errors={errors.fields.email}
          />
          <Honeypot />
          <CaptchaBox
            box={captchaBox}
            shown={captcha.shown}
            challenged={captcha.challenged}
            solved={captcha.solved}
            failed={captcha.failed}
          />
          <Button type="submit" busy={request.isPending} busyLabel="Sending the link">
            Send me a code
          </Button>
          {captcha.enabled && <CaptchaNotice />}
        </form>
      )}
      <p className="mt-6 text-text-muted">
        Remembered it? <TextLink to="/signin">Back to sign in</TextLink>
      </p>
    </AuthLayout>
  );
}
