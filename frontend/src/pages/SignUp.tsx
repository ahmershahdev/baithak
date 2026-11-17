import { useMutation } from "@tanstack/react-query";
import { useState, type SubmitEvent } from "react";
import { Link } from "react-router";

import { api, readErrors, type ApiErrors } from "../api/client";
import { AuthCard, Button, ErrorMessage, Field, Notice } from "../components/ui";
import { textField } from "../forms";

interface SignUpBody {
  email: string;
  username: string;
  display_name: string;
  password: string;
}

export function SignUp() {
  const [errors, setErrors] = useState<ApiErrors>({ fields: {} });
  const [sentTo, setSentTo] = useState<string | null>(null);

  const signUp = useMutation({
    mutationFn: async (body: SignUpBody) => api.POST("/api/v1/auth/signup/", { body }),
    onSuccess: ({ response, error }, body) => {
      if (response.status === 202) setSentTo(body.email);
      else setErrors(readErrors(error));
    },
    onError: () => {
      setErrors({ detail: "Could not reach Baithak. Try again.", fields: {} });
    },
  });

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setErrors({ fields: {} });
    signUp.mutate({
      email: textField(form, "email"),
      username: textField(form, "username"),
      display_name: textField(form, "display_name"),
      password: textField(form, "password"),
    });
  }

  if (sentTo !== null) {
    return (
      <AuthCard title="Check your email">
        <Notice>
          We sent a link to <strong>{sentTo}</strong>. Open it to confirm your email and sign in.
        </Notice>
        <p className="mt-5 text-sm text-text-muted">
          Already confirmed?{" "}
          <Link className="text-accent-text underline" to="/signin">
            Sign in
          </Link>
        </p>
      </AuthCard>
    );
  }

  return (
    <AuthCard title="Create an account">
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
          label="Handle"
          name="username"
          autoComplete="username"
          autoCapitalize="none"
          spellCheck={false}
          required
          hint="What people type after @ to mention you. Lowercase letters, digits, dots, hyphens and underscores."
          errors={errors.fields.username}
        />
        <Field
          label="Display name (optional)"
          name="display_name"
          autoComplete="name"
          errors={errors.fields.display_name}
        />
        <Field
          label="Password"
          name="password"
          type="password"
          autoComplete="new-password"
          required
          hint="At least 8 characters, not only digits, not a common password."
          errors={errors.fields.password}
        />
        <Button type="submit" disabled={signUp.isPending}>
          {signUp.isPending ? "Creating account" : "Create account"}
        </Button>
      </form>
      <p className="mt-5 text-sm text-text-muted">
        Have an account?{" "}
        <Link className="text-accent-text underline" to="/signin">
          Sign in
        </Link>
      </p>
    </AuthCard>
  );
}
