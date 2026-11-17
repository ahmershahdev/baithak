import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState, type SubmitEvent } from "react";
import { useSearchParams } from "react-router";

import { api, readErrors, type ApiErrors } from "../api/client";
import { useCaptcha } from "../captcha";
import { CaptchaBox, CaptchaNotice } from "../components/CaptchaBox";
import { PasswordField } from "../components/PasswordField";
import {
  AuthLayout,
  Button,
  ErrorMessage,
  Field,
  Honeypot,
  Notice,
  TextLink,
} from "../components/ui";
import { useAvailability } from "../availability";
import { honeypot, textField } from "../forms";
import { meetsRules } from "../passwords";
import { rememberNext, safePath } from "../next";

interface SignUpBody {
  email: string;
  username: string;
  display_name: string;
  password: string;
  website: string;
}

function Available() {
  return (
    <p className="flex items-center gap-1.5 text-sm font-medium text-success" role="status">
      <svg viewBox="0 0 16 16" className="size-4" aria-hidden="true">
        <path
          d="M3.5 8.5l3 3 6-7"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      Available
    </p>
  );
}

export function SignUp() {
  const captchaBox = useRef<HTMLDivElement>(null);
  const captcha = useCaptcha("signup", captchaBox);
  const [params] = useSearchParams();
  const next = safePath(params.get("next"));
  const [errors, setErrors] = useState<ApiErrors>({ fields: {} });

  // Kept for after the confirmation email, which signs the person in in this tab.
  useEffect(() => {
    rememberNext(next);
  }, [next]);
  const [sentTo, setSentTo] = useState<string | null>(null);
  // Kept as the person types so the strength meter can mark a password built from them.
  const [about, setAbout] = useState({ email: "", username: "", name: "" });
  const emailCheck = useAvailability("email", about.email);
  const handleCheck = useAvailability("username", about.username);

  const signUp = useMutation({
    mutationFn: async (body: SignUpBody) =>
      api.POST("/api/v1/auth/signup/", { body: { ...body, ...(await captcha.tokens()) } }),
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
    if (!meetsRules(textField(form, "password"))) {
      setErrors({ fields: { password: ["Meet every rule below first."] } });
      return;
    }
    if (handleCheck?.available === false) {
      setErrors({ fields: { username: [handleCheck.message] } });
      return;
    }
    setErrors({ fields: {} });
    signUp.mutate({
      email: textField(form, "email"),
      username: textField(form, "username"),
      display_name: textField(form, "display_name"),
      password: textField(form, "password"),
      ...honeypot(form),
    });
  }

  if (sentTo !== null) {
    return (
      <AuthLayout title="Check your email">
        <Notice>
          We sent a link to <strong>{sentTo}</strong>. Open it to confirm your email and sign in.
        </Notice>
        <p className="mt-6 text-text-muted">
          Already confirmed? <TextLink to="/signin">Sign in</TextLink>
        </p>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title="Make yourself at home"
      intro={
        <>
          Have an account?{" "}
          <TextLink to={next ? `/signin?next=${encodeURIComponent(next)}` : "/signin"}>
            Sign in
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
          errors={
            errors.fields.email ??
            (emailCheck?.available === false ? [emailCheck.message] : undefined)
          }
          below={emailCheck?.available && <Available />}
          onChange={(event) => {
            setAbout((now) => ({ ...now, email: event.target.value }));
          }}
        />
        <div className="grid gap-5 sm:grid-cols-2">
          <Field
            label="Handle"
            name="username"
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            placeholder="amna"
            required
            errors={
              errors.fields.username ??
              (handleCheck?.available === false ? [handleCheck.message] : undefined)
            }
            below={handleCheck?.available && <Available />}
            onChange={(event) => {
              setAbout((now) => ({ ...now, username: event.target.value }));
            }}
          />
          <Field
            label="Display name"
            name="display_name"
            autoComplete="name"
            placeholder="Amna Khan"
            errors={errors.fields.display_name}
            onChange={(event) => {
              setAbout((now) => ({ ...now, name: event.target.value }));
            }}
          />
        </div>
        <p className="-mt-3 text-sm text-text-subtle">
          Your handle is what people type after @. Lowercase letters, digits, dots, hyphens and
          underscores. The display name is optional.
        </p>
        <PasswordField
          label="Password"
          name="password"
          autoComplete="new-password"
          placeholder="Strong and easy for you to remember"
          required
          errors={errors.fields.password}
          meterWith={[about.email, about.username, about.name, "baithak"]}
        />
        <Honeypot />
        <CaptchaBox
          box={captchaBox}
          shown={captcha.shown}
          challenged={captcha.challenged}
          solved={captcha.solved}
          failed={captcha.failed}
        />
        <Button
          type="submit"
          busy={signUp.isPending}
          busyLabel="Creating your account"
          className="mt-1"
        >
          Create account
        </Button>
        {captcha.enabled && <CaptchaNotice />}
      </form>
    </AuthLayout>
  );
}
