import { useMutation } from "@tanstack/react-query";
import { useState, type SubmitEvent } from "react";
import { useSearchParams } from "react-router";

import { api, readErrors, type ApiErrors } from "../api/client";
import { PasswordField } from "../components/PasswordField";
import { AuthLayout, Button, ErrorMessage, Notice, TextLink } from "../components/ui";
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
      <AuthLayout title="Password changed">
        <Notice>Your password is changed. Other devices are signed out.</Notice>
        <p className="mt-6">
          <TextLink to="/signin">Sign in</TextLink>
        </p>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Choose a new password">
      <form onSubmit={submit} className="flex flex-col gap-5" noValidate>
        {errors.detail && (
          <ErrorMessage>
            {errors.detail} <TextLink to="/forgot-password">Ask for a new link</TextLink>
          </ErrorMessage>
        )}
        <PasswordField
          label="New password"
          name="password"
          autoComplete="new-password"
          placeholder="At least 8 characters"
          required
          errors={errors.fields.password}
          meterWith={["baithak"]}
        />
        <Button type="submit" busy={reset.isPending} busyLabel="Saving" disabled={!uid || !token}>
          Save password
        </Button>
      </form>
    </AuthLayout>
  );
}
