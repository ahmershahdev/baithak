import { useMutation } from "@tanstack/react-query";
import { useState, type SubmitEvent } from "react";
import { Link, useNavigate } from "react-router";

import { api, readErrors, type ApiErrors } from "../api/client";
import { useSetMe } from "../auth";
import { AuthCard, Button, ErrorMessage, Field } from "../components/ui";
import { textField } from "../forms";

export function SignIn() {
  const navigate = useNavigate();
  const setMe = useSetMe();
  const [errors, setErrors] = useState<ApiErrors>({ fields: {} });

  const signIn = useMutation({
    mutationFn: async (body: { email: string; password: string }) =>
      api.POST("/api/v1/auth/signin/", { body }),
    onSuccess: ({ data, error }) => {
      if (data) {
        setMe(data);
        void navigate("/");
      } else {
        setErrors(readErrors(error));
      }
    },
    onError: () => {
      setErrors({ detail: "Could not reach Baithak. Try again.", fields: {} });
    },
  });

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    signIn.mutate({ email: textField(form, "email"), password: textField(form, "password") });
  }

  return (
    <AuthCard title="Sign in">
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
        <Field
          label="Password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          errors={errors.fields.password}
        />
        <Button type="submit" disabled={signIn.isPending}>
          {signIn.isPending ? "Signing in" : "Sign in"}
        </Button>
      </form>
      <div className="mt-5 flex flex-col gap-2 text-sm">
        <Link className="text-accent-text underline" to="/forgot-password">
          Forgot your password?
        </Link>
        <p className="text-text-muted">
          New here?{" "}
          <Link className="text-accent-text underline" to="/signup">
            Create an account
          </Link>
        </p>
      </div>
    </AuthCard>
  );
}
