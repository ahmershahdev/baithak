import { useMutation } from "@tanstack/react-query";
import { useRef, useState, type SubmitEvent } from "react";

import { api, readErrors, type ApiErrors } from "../api/client";
import { useCaptcha } from "../captcha";
import { CaptchaBox } from "../components/CaptchaBox";
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
      if (problems.captcha) void captcha.challenge();
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
      intro="It happens. We will send you a link to choose a new one."
    >
      {sentTo !== null ? (
        <Notice>
          If <strong>{sentTo}</strong> has an account, a reset link is on its way.
        </Notice>
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
          <CaptchaBox box={captchaBox} challenged={captcha.challenged} solved={captcha.solved} />
          <Button type="submit" busy={request.isPending} busyLabel="Sending the link">
            Send reset link
          </Button>
        </form>
      )}
      <p className="mt-6 text-text-muted">
        Remembered it? <TextLink to="/signin">Back to sign in</TextLink>
      </p>
    </AuthLayout>
  );
}
