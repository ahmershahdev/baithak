import { useMutation } from "@tanstack/react-query";
import { useState, type SubmitEvent } from "react";
import { Link } from "react-router";

import { api, readErrors, type ApiErrors } from "../api/client";
import { AuthCard, Button, ErrorMessage, Field, Notice } from "../components/ui";
import { textField } from "../forms";

export function ForgotPassword() {
  const [errors, setErrors] = useState<ApiErrors>({ fields: {} });
  const [sentTo, setSentTo] = useState<string | null>(null);

  const request = useMutation({
    mutationFn: async (email: string) =>
      api.POST("/api/v1/auth/password-reset/", { body: { email } }),
    onSuccess: ({ response, error }, email) => {
      if (response.status === 202) setSentTo(email);
      else setErrors(readErrors(error));
    },
    onError: () => {
      setErrors({ detail: "Could not reach Baithak. Try again.", fields: {} });
    },
  });

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    request.mutate(textField(new FormData(event.currentTarget), "email"));
  }

  return (
    <AuthCard title="Reset your password">
      {sentTo !== null ? (
        <Notice>
          If <strong>{sentTo}</strong> has an account, a reset link is on its way.
        </Notice>
      ) : (
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          {errors.detail && <ErrorMessage>{errors.detail}</ErrorMessage>}
          <Field
            label="Email"
            name="email"
            type="email"
            autoComplete="email"
            required
            errors={errors.fields.email}
          />
          <Button type="submit" disabled={request.isPending}>
            {request.isPending ? "Sending" : "Send reset link"}
          </Button>
        </form>
      )}
      <p className="mt-5 text-sm text-text-muted">
        <Link className="text-accent-text underline" to="/signin">
          Back to sign in
        </Link>
      </p>
    </AuthCard>
  );
}
