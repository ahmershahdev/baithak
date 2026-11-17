import { useMutation } from "@tanstack/react-query";
import { useState, type SubmitEvent } from "react";
import { Link, useSearchParams } from "react-router";

import { api, readErrors, type ApiErrors } from "../api/client";
import { AuthCard, Button, ErrorMessage, Field, Notice } from "../components/ui";
import { textField } from "../forms";

export function ResetPassword() {
  const [params] = useSearchParams();
  const [errors, setErrors] = useState<ApiErrors>({ fields: {} });
  const [done, setDone] = useState(false);
  const uid = params.get("uid") ?? "";
  const token = params.get("token") ?? "";

  const reset = useMutation({
    mutationFn: async (password: string) =>
      api.POST("/api/v1/auth/password-reset/confirm/", { body: { uid, token, password } }),
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
    setErrors({ fields: {} });
    reset.mutate(textField(new FormData(event.currentTarget), "password"));
  }

  if (done) {
    return (
      <AuthCard title="Password changed">
        <Notice>Your password is changed. Other devices are signed out.</Notice>
        <p className="mt-5 text-sm">
          <Link className="text-accent-text underline" to="/signin">
            Sign in
          </Link>
        </p>
      </AuthCard>
    );
  }

  return (
    <AuthCard title="Choose a new password">
      <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
        {errors.detail && (
          <ErrorMessage>
            {errors.detail}{" "}
            <Link className="underline" to="/forgot-password">
              Ask for a new link
            </Link>
          </ErrorMessage>
        )}
        <Field
          label="New password"
          name="password"
          type="password"
          autoComplete="new-password"
          required
          hint="At least 8 characters, not only digits, not a common password."
          errors={errors.fields.password}
        />
        <Button type="submit" disabled={reset.isPending || !uid || !token}>
          {reset.isPending ? "Saving" : "Save password"}
        </Button>
      </form>
    </AuthCard>
  );
}
