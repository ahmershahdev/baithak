import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState, type SubmitEvent } from "react";
import { useNavigate, useSearchParams } from "react-router";

import { api, readErrors, type ApiErrors } from "../api/client";
import { useSetMe } from "../auth";
import { useCaptcha } from "../captcha";
import { CaptchaBox, CaptchaNotice } from "../components/CaptchaBox";
import { PasswordField } from "../components/PasswordField";
import { AuthLayout, Button, ErrorMessage, Field, Honeypot, TextLink } from "../components/ui";
import { honeypot, textField } from "../forms";
import { rememberNext, safePath, takeNext } from "../next";

interface SignInBody {
  email: string;
  password: string;
  website: string;
}

export function SignIn() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = safePath(params.get("next"));
  const setMe = useSetMe();
  const captchaBox = useRef<HTMLDivElement>(null);
  const captcha = useCaptcha("signin", captchaBox);
  const [errors, setErrors] = useState<ApiErrors>({ fields: {} });

  useEffect(() => {
    rememberNext(next);
  }, [next]);

  const signIn = useMutation({
    mutationFn: async (body: SignInBody) =>
      api.POST("/api/v1/auth/signin/", { body: { ...body, ...(await captcha.tokens()) } }),
    onSuccess: ({ data, error }) => {
      if (data) {
        setMe(data);
        void navigate(takeNext());
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
    signIn.mutate({
      email: textField(form, "email"),
      password: textField(form, "password"),
      ...honeypot(form),
    });
  }

  return (
    <AuthLayout
      title="Welcome back"
      intro={
        <>
          New here?{" "}
          <TextLink to={next ? `/signup?next=${encodeURIComponent(next)}` : "/signup"}>
            Create an account
          </TextLink>
        </>
      }
    >
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
        <div className="flex flex-col gap-2">
          <PasswordField
            label="Password"
            name="password"
            autoComplete="current-password"
            placeholder="Your password"
            required
            errors={errors.fields.password}
          />
          <TextLink to="/forgot-password" className="self-end text-sm">
            Forgot your password?
          </TextLink>
        </div>
        <Honeypot />
        <CaptchaBox
          box={captchaBox}
          challenged={captcha.challenged}
          solved={captcha.solved}
          failed={captcha.failed}
        />
        <Button type="submit" busy={signIn.isPending} busyLabel="Signing in" className="mt-1">
          Sign in
        </Button>
        {captcha.enabled && <CaptchaNotice />}
      </form>
    </AuthLayout>
  );
}
