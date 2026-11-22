import type { ReactNode } from "react";

import { AuthLayout } from "../components/ui";
import { SUPPORT_EMAIL } from "../contact";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="font-display text-xl font-semibold tracking-tight">{title}</h2>
      <div className="flex flex-col gap-2 text-text-muted">{children}</div>
    </section>
  );
}

function Out({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a
      className="font-semibold text-accent-text underline"
      href={href}
      target="_blank"
      rel="noreferrer"
    >
      {children}
    </a>
  );
}

export function Privacy() {
  const support = (
    <a className="font-semibold text-accent-text underline" href={`mailto:${SUPPORT_EMAIL}`}>
      {SUPPORT_EMAIL}
    </a>
  );
  return (
    <AuthLayout
      title="Privacy"
      intro="What Baithak keeps, who else sees it, and how to have it removed."
    >
      <div className="flex flex-col gap-8">
        <Section title="What we keep">
          <p>
            Your account: email address, handle, display name, time zone and notification settings.
            Your password is stored only as an Argon2id hash, never as you typed it.
          </p>
          <p>
            What you add to a workspace: messages, replies, reactions, files and issues. A deleted
            message loses its text; an empty row stays so threads and counts still add up. Changes
            to workspaces, members and roles are kept in an audit log that the workspace&rsquo;s
            admins can read.
          </p>
        </Section>

        <Section title="Cookies">
          <p>
            Two cookies: one keeps you signed in, the other protects forms against cross-site
            requests. No advertising or analytics cookies. Your browser also remembers the last
            workspace you opened, so Baithak can take you back to it.
          </p>
        </Section>

        <Section title="Who else sees it">
          <p>
            People in your workspace see what you post in the channels they can read. Private
            channels and direct messages are seen only by the people in them.
          </p>
          <p>
            Sign-in, sign-up, password reset and the contact form are protected by Google reCAPTCHA.
            Google receives details about your browser and device and your IP address, under
            Google&rsquo;s <Out href="https://policies.google.com/privacy">Privacy Policy</Out> and{" "}
            <Out href="https://policies.google.com/terms">Terms of Service</Out>.
          </p>
          <p>
            Emails (address confirmation, reset codes, notification digests, contact form messages)
            are sent through <Out href="https://resend.com/legal/privacy-policy">Resend</Out>, which
            handles your email address and the message.
          </p>
          <p>
            If a workspace admin connects a GitHub repository or an incoming webhook to a channel,
            the events they send are posted there. Nothing is sold, and there are no ads.
          </p>
        </Section>

        <Section title="How long">
          <p>
            Your account and workspace content stay until they are removed. Invitations expire after
            7 days, password reset codes after 10 minutes, and webhook delivery logs are deleted
            after 30 days.
          </p>
        </Section>

        <Section title="Deleting your account">
          <p>
            You can delete your account yourself, under Settings in any workspace, by confirming
            your password. Your account, sign-in, settings, reactions and notifications are removed
            for good, and you leave every workspace. Messages, files and issues you posted in
            workspaces shared with others stay there, shown as from a deleted account, so the
            conversations around them still make sense. Workspaces where you are the only member are
            deleted with everything in them. If you are the last owner of a workspace that has other
            people, make someone else an owner first.
          </p>
        </Section>

        <Section title="Your choices">
          <p>
            Email notifications can be turned off, or held during quiet hours, in your settings. For
            a copy of your data, a correction, or to have something you posted removed, email{" "}
            {support}. We reply within two weeks.
          </p>
        </Section>

        <p className="text-sm text-text-subtle">Last updated 22 November 2026.</p>
      </div>
    </AuthLayout>
  );
}
