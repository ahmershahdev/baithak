import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";

import { api, readErrors } from "../api/client";
import { useSetMe } from "../auth";
import { AuthCard, Button, ErrorMessage } from "../components/ui";

// Confirming takes a click rather than happening on load: mail scanners open links, and the
// link only works once.
export function VerifyEmail() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const setMe = useSetMe();
  const [error, setError] = useState<string | null>(null);
  const uid = params.get("uid") ?? "";
  const token = params.get("token") ?? "";

  const verify = useMutation({
    mutationFn: async () => api.POST("/api/v1/auth/verify-email/", { body: { uid, token } }),
    onSuccess: ({ data, error: apiError }) => {
      if (data) {
        setMe(data);
        void navigate("/");
      } else {
        setError(readErrors(apiError).detail ?? "This link is not valid or has expired.");
      }
    },
    onError: () => {
      setError("Could not reach Baithak. Try again.");
    },
  });

  return (
    <AuthCard title="Confirm your email">
      <div className="flex flex-col gap-4">
        {error && <ErrorMessage>{error}</ErrorMessage>}
        {uid && token ? (
          <Button
            type="button"
            onClick={() => {
              verify.mutate();
            }}
            disabled={verify.isPending}
          >
            {verify.isPending ? "Confirming" : "Confirm email and sign in"}
          </Button>
        ) : (
          <ErrorMessage>
            This link is missing its code. Open the link from the email again.
          </ErrorMessage>
        )}
        <p className="text-sm text-text-muted">
          Link expired?{" "}
          <Link className="text-accent-text underline" to="/signin">
            Sign in
          </Link>{" "}
          and ask for a new one.
        </p>
      </div>
    </AuthCard>
  );
}
