import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router";

import { useMe } from "./auth";
import { ErrorMessage } from "./components/ui";
import { ForgotPassword } from "./pages/ForgotPassword";
import { Home } from "./pages/Home";
import { ResetPassword } from "./pages/ResetPassword";
import { SignIn } from "./pages/SignIn";
import { SignUp } from "./pages/SignUp";
import { VerifyEmail } from "./pages/VerifyEmail";

function Loading() {
  return (
    <p role="status" className="p-8 text-text-muted">
      Loading
    </p>
  );
}

function SignedOutOnly({ children }: { children: ReactNode }) {
  const me = useMe();
  if (me.isPending) return <Loading />;
  if (me.data) return <Navigate to="/" replace />;
  return children;
}

function HomeRoute() {
  const me = useMe();
  if (me.isPending) return <Loading />;
  if (me.isError) {
    return (
      <main className="mx-auto max-w-sm px-4 py-12">
        <ErrorMessage>Could not reach Baithak. Is the backend running?</ErrorMessage>
      </main>
    );
  }
  if (me.data === null) return <Navigate to="/signin" replace />;
  return <Home user={me.data} />;
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<HomeRoute />} />
      <Route
        path="/signin"
        element={
          <SignedOutOnly>
            <SignIn />
          </SignedOutOnly>
        }
      />
      <Route
        path="/signup"
        element={
          <SignedOutOnly>
            <SignUp />
          </SignedOutOnly>
        }
      />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="/verify-email" element={<VerifyEmail />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
