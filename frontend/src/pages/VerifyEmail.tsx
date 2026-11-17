import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router";

import { api, readErrors } from "../api/client";
import { useSetMe } from "../auth";
import { AuthLayout, Button, ErrorMessage, TextLink } from "../components/ui";

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
    <AuthLayout title="One last step" intro="Confirm your email and you are in.">
      <div className="flex flex-col gap-5">
        {error && <ErrorMessage>{error}</ErrorMessage>}
        {uid && token ? (
          <Button
            type="button"
            busy={verify.isPending}
            busyLabel="Confirming"
            onClick={() => {
              verify.mutate();
            }}
          >
            Confirm email and sign in
          </Button>
        ) : (
          <ErrorMessage>
            This link is missing its code. Open the link from the email again.
          </ErrorMessage>
        )}
        <p className="text-text-muted">
          Link expired? <TextLink to="/signin">Sign in</TextLink> and ask for a new one.
        </p>
      </div>
    </AuthLayout>
  );
}
