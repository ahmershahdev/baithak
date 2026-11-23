import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState, type SubmitEvent } from "react";
import { useNavigate, useSearchParams } from "react-router";

import { api, readErrors, type ApiErrors, type User } from "../api/client";
import { useSetMe } from "../auth";
import { useCaptcha } from "../captcha";
import { CaptchaBox, CaptchaNotice } from "../components/CaptchaBox";
import { PasswordField } from "../components/PasswordField";
import { ProviderSignIn } from "../components/ProviderSignIn";
import {
  AuthLayout,
  Button,
  ErrorMessage,
  Field,
  Honeypot,
  QuietButton,
  TextLink,
} from "../components/ui";
import { honeypot, textField } from "../forms";
import { rememberNext, safePath, takeNext } from "../next";
import { PROVIDER_PROBLEMS } from "../providers";

interface SignInBody {
  email: string;
  password: string;
  website: string;
}

const UNREACHABLE: ApiErrors = { detail: "Could not reach Baithak. Try again.", fields: {} };

function CodeStep({
  onSignedIn,
  onStartOver,
}: {
  onSignedIn: (user: User) => void;
  onStartOver: () => void;
}) {
  const [recovery, setRecovery] = useState(false);
  const [errors, setErrors] = useState<ApiErrors>({ fields: {} });

  const verify = useMutation({
    mutationFn: async (code: string) =>
      api.POST("/api/v1/auth/signin/two-step/", { body: { code } }),
    onSuccess: ({ data, error }) => {
      if (data) {
        onSignedIn(data);
        return;
      }
      setErrors(readErrors(error));
    },
    onError: () => {
      setErrors(UNREACHABLE);
    },
  });

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrors({ fields: {} });
    verify.mutate(textField(new FormData(event.currentTarget), "code"));
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-5" noValidate>
      {errors.detail && <ErrorMessage>{errors.detail}</ErrorMessage>}
      {recovery ? (
        <Field
          key="recovery"
          label="Recovery code"
          name="code"
          autoComplete="off"
          autoCapitalize="none"
          spellCheck={false}
          placeholder="xxxxx-xxxxx"
          hint="One of the codes you saved when you turned on two-step sign-in. Each works once."
          required
          autoFocus
          errors={errors.fields.code}
        />
      ) : (
        <Field
          key="app"
          label="Code from your authenticator app"
          name="code"
          inputMode="numeric"
          autoComplete="one-time-code"
          pattern="[0-9 ]*"
          maxLength={7}
          placeholder="123 456"
          required
          autoFocus
          className="text-center font-mono text-2xl tracking-[0.4em]"
          errors={errors.fields.code}
        />
      )}
      <Button type="submit" busy={verify.isPending} busyLabel="Checking">
        Sign in
      </Button>
      <div className="flex flex-wrap justify-between gap-2 text-sm">
        <QuietButton
          type="button"
          onClick={() => {
            setErrors({ fields: {} });
            setRecovery((now) => !now);
          }}
        >
          {recovery ? "Use the authenticator app" : "Use a recovery code"}
        </QuietButton>
        <QuietButton type="button" onClick={onStartOver}>
          Start over
        </QuietButton>
      </div>
    </form>
  );
}

export function SignIn() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = safePath(params.get("next"));
  const setMe = useSetMe();
  const captchaBox = useRef<HTMLDivElement>(null);
  const captcha = useCaptcha("signin", captchaBox);
  const [errors, setErrors] = useState<ApiErrors>(() => {
    const problem = PROVIDER_PROBLEMS[params.get("error") ?? ""];
    return problem ? { detail: problem, fields: {} } : { fields: {} };
  });
  const [needsCode, setNeedsCode] = useState(false);

  useEffect(() => {
    rememberNext(next);
  }, [next]);

  function finish(user: User) {
    setMe(user);
    void navigate(takeNext());
  }

  const signIn = useMutation({
    mutationFn: async (body: SignInBody) =>
      api.POST("/api/v1/auth/signin/", { body: { ...body, ...(await captcha.tokens()) } }),
    onSuccess: ({ data, error }) => {
      if (data && "two_step" in data) {
        setNeedsCode(true);
        return;
      }
      if (data) {
        finish(data);
        return;
      }
      const problems = readErrors(error);
      setErrors(problems);
      if (problems.captcha) captcha.challenge();
    },
    onError: () => {
      setErrors(UNREACHABLE);
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

  if (needsCode) {
    return (
      <AuthLayout
        title="One more step"
        intro="Your account has two-step sign-in. Open your authenticator app for the code."
      >
        <CodeStep
          onSignedIn={finish}
          onStartOver={() => {
            setNeedsCode(false);
          }}
        />
      </AuthLayout>
    );
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
        <ProviderSignIn next={next} />
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
          shown={captcha.shown}
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
