import { useMutation } from "@tanstack/react-query";
import { useState, type SubmitEvent } from "react";
import { useLocation, useSearchParams } from "react-router";

import { api, readErrors, type ApiErrors } from "../api/client";
import { PasswordField } from "../components/PasswordField";
import { AuthLayout, Button, ErrorMessage, Field, Notice, TextLink } from "../components/ui";
import { textField } from "../forms";
import { meetsRules } from "../passwords";

interface ResetBody {
  uid?: string;
  email?: string;
  code: string;
  password: string;
}

export function ResetPassword() {
  const [params] = useSearchParams();
  const location = useLocation();
  const uid = params.get("uid") ?? "";
  const linkCode = params.get("code") ?? "";
  // From the forgot-password page, carried in router state so the address never sits in a URL.
  const knownEmail = (location.state as { email?: string } | null)?.email ?? "";
  const [errors, setErrors] = useState<ApiErrors>({ fields: {} });
  const [done, setDone] = useState(false);

  const reset = useMutation({
    mutationFn: async (body: ResetBody) =>
      api.POST("/api/v1/auth/password-reset/confirm/", { body }),
    onSuccess: ({ response, error }) => {
      if (response.status === 204) setDone(true);
      else setErrors(readErrors(error));
    },
    onError: () => {
      setErrors({ detail: "Could not reach Baithak. Try again.", fields: {} });
    },
  });

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const password = textField(form, "password");
    if (!meetsRules(password)) {
      setErrors({ fields: { password: ["Meet every rule below first."] } });
      return;
    }
    setErrors({ fields: {} });
    reset.mutate({
      ...(uid ? { uid } : { email: textField(form, "email") }),
      code: textField(form, "code").replace(/\D/g, ""),
      password,
    });
  }

  if (done) {
    return (
      <AuthLayout title="Password changed">
        <Notice>Your password is changed, and every other device is signed out.</Notice>
        <p className="mt-6">
          <TextLink to="/signin">Sign in</TextLink>
        </p>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title="Choose a new password"
      intro="Enter the 6-digit code from the email. It works once and expires after 10 minutes."
    >
      <form onSubmit={submit} className="flex flex-col gap-5" noValidate>
        {errors.detail && (
          <ErrorMessage>
            {errors.detail} <TextLink to="/forgot-password">Send a new code</TextLink>
          </ErrorMessage>
        )}
        {!uid && (
          <Field
            label="Email"
            name="email"
            type="email"
            inputMode="email"
            autoComplete="email"
            placeholder="you@company.com"
            defaultValue={knownEmail}
            required
            errors={errors.fields.email}
          />
        )}
        <Field
          label="Code"
          name="code"
          inputMode="numeric"
          autoComplete="one-time-code"
          pattern="\d{6}"
          maxLength={6}
          placeholder="123456"
          defaultValue={linkCode}
          className="font-mono text-lg tracking-[0.4em]"
          required
          errors={errors.fields.code}
        />
        <PasswordField
          label="New password"
          name="password"
          autoComplete="new-password"
          placeholder="Strong and easy for you to remember"
          required
          errors={errors.fields.password}
          meterWith={["baithak", knownEmail]}
        />
        <Button type="submit" busy={reset.isPending} busyLabel="Saving">
          Save password
        </Button>
      </form>
    </AuthLayout>
  );
}
