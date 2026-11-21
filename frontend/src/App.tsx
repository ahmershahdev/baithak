import type { ReactNode } from "react";
import { Navigate, Route, Routes, useLocation, useSearchParams } from "react-router";

import type { User } from "./api/client";
import { useWorkspaces } from "./api/workspaces";
import { useMe } from "./auth";
import { lastWorkspace } from "./lastWorkspace";
import { ErrorMessage } from "./components/ui";
import { Contact } from "./pages/Contact";
import { ForgotPassword } from "./pages/ForgotPassword";
import { Home } from "./pages/Home";
import { Invite } from "./pages/Invite";
import { ResetPassword } from "./pages/ResetPassword";
import { SignIn } from "./pages/SignIn";
import { SignUp } from "./pages/SignUp";
import { VerifyEmail } from "./pages/VerifyEmail";
import { Audit } from "./pages/workspace/Audit";
import { Channels } from "./pages/workspace/Channels";
import { ChannelView } from "./pages/workspace/ChannelView";
import { Notifications } from "./pages/workspace/Notifications";
import { Search } from "./pages/workspace/Search";
import { StartConversation } from "./pages/workspace/StartConversation";
import { Invitations } from "./pages/workspace/Invitations";
import { Members } from "./pages/workspace/Members";
import { Overview } from "./pages/workspace/Overview";
import { Settings } from "./pages/workspace/Settings";
import { WorkspaceShell } from "./pages/workspace/Shell";
import { safePath } from "./next";

function Loading() {
  return (
    <p role="status" className="p-8 text-text-muted">
      Loading
    </p>
  );
}

function Unreachable() {
  return (
    <main className="mx-auto max-w-sm px-4 py-12">
      <ErrorMessage>Could not reach Baithak. Is the backend running?</ErrorMessage>
    </main>
  );
}

function SignedOutOnly({ children }: { children: ReactNode }) {
  const me = useMe();
  const [params] = useSearchParams();
  if (me.isPending) return <Loading />;
  // The page signs the person in and goes to `next` at the same moment this sees them signed
  // in; both must go to the same place, or an invitation is lost to whichever runs last.
  if (me.data) return <Navigate to={safePath(params.get("next")) ?? "/"} replace />;
  return children;
}

function SignedIn({ children }: { children: (me: User) => ReactNode }) {
  const me = useMe();
  const location = useLocation();
  if (me.isPending) return <Loading />;
  if (me.isError) return <Unreachable />;
  if (me.data === null) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={location.pathname === "/" ? "/signin" : `/signin?next=${next}`} replace />;
  }
  return children(me.data);
}

function HomeRoute({ me }: { me: User }) {
  const workspaces = useWorkspaces();
  if (workspaces.isPending) return <Loading />;
  if (workspaces.isError) return <Unreachable />;
  const last = lastWorkspace();
  const open = workspaces.data.find((w) => w.slug === last) ?? workspaces.data[0];
  if (open) return <Navigate to={`/w/${open.slug}`} replace />;
  return <Home user={me} />;
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<SignedIn>{(me) => <HomeRoute me={me} />}</SignedIn>} />
      <Route path="/w/new" element={<SignedIn>{(me) => <Home user={me} adding />}</SignedIn>} />
      <Route path="/w/:slug" element={<SignedIn>{(me) => <WorkspaceShell me={me} />}</SignedIn>}>
        <Route index element={<Overview />} />
        <Route path="channels" element={<Channels />} />
        <Route path="c/:channelId" element={<ChannelView />} />
        <Route path="dm" element={<StartConversation />} />
        <Route path="search" element={<Search />} />
        <Route path="notifications" element={<Notifications />} />
        <Route path="members" element={<Members />} />
        <Route path="invitations" element={<Invitations />} />
        <Route path="settings" element={<Settings />} />
        <Route path="audit" element={<Audit />} />
      </Route>
      <Route path="/invite" element={<Invite />} />
      <Route path="/contact" element={<Contact />} />
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
