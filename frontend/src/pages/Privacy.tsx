import type { ReactNode } from "react";

import { DocLayout, type DocSection } from "../components/DocLayout";
import { SUPPORT_EMAIL } from "../contact";

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

function Support() {
  return (
    <a className="font-semibold text-accent-text underline" href={`mailto:${SUPPORT_EMAIL}`}>
      {SUPPORT_EMAIL}
    </a>
  );
}

function Table({ head, rows }: { head: [string, string]; rows: [ReactNode, ReactNode][] }) {
  return (
    <div className="overflow-x-auto rounded-2xl border border-border">
      <table className="w-full text-left text-sm">
        <thead className="bg-bg-subtle text-text">
          <tr>
            {head.map((cell) => (
              <th key={cell} scope="col" className="px-4 py-2.5 font-semibold">
                {cell}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map(([what, detail], index) => (
            <tr key={index} className="align-top">
              <th scope="row" className="px-4 py-2.5 font-semibold text-text">
                {what}
              </th>
              <td className="px-4 py-2.5">{detail}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Points({ items }: { items: ReactNode[] }) {
  return (
    <ul className="flex list-disc flex-col gap-2 pl-5 marker:text-text-subtle">
      {items.map((item, index) => (
        <li key={index}>{item}</li>
      ))}
    </ul>
  );
}

const SHORT = [
  ["No ads, no selling", "Nothing you write is sold, used for ads or used to train AI."],
  ["Only what is needed", "We keep what Baithak needs to work, and nothing to track you."],
  ["Yours to delete", "Delete your account yourself, any time, from Settings."],
  ["A person answers", "Write to us and you get a reply within two weeks."],
] as const;

const SECTIONS: DocSection[] = [
  {
    id: "in-short",
    title: "In short",
    body: (
      <ul className="grid gap-3 sm:grid-cols-2">
        {SHORT.map(([title, text]) => (
          <li key={title} className="rounded-2xl border border-border bg-surface p-4">
            <p className="font-semibold text-text">{title}</p>
            <p className="mt-1 text-sm">{text}</p>
          </li>
        ))}
      </ul>
    ),
  },
  {
    id: "who-we-are",
    title: "Who we are",
    body: (
      <p>
        Baithak is made and run by Syed Ahmer Shah (
        <Out href="https://ahmershah.dev">ahmershah.dev</Out>
        ), who decides how the data described here is used. Questions about this page, or about your
        data, go to <Support />.
      </p>
    ),
  },
  {
    id: "what-we-keep",
    title: "What we keep",
    body: (
      <>
        <Table
          head={["What", "Details"]}
          rows={[
            [
              "Your account",
              "Email address, handle, display name, time zone, notification settings and quiet hours. Your password is stored only as an Argon2id hash, never as you typed it. If you turn on two-step sign-in, its key is stored encrypted and your recovery codes only as hashes.",
            ],
            [
              "What you post",
              "Messages, replies, reactions, files and issues in your workspaces, and when you last read each channel, so unread counts match on every device.",
            ],
            [
              "Files",
              "Files are kept encrypted, as you uploaded them, once a virus scan passes them. For images we also make a smaller preview with the photo's hidden details (such as camera and location data) removed. A file that fails the scan is deleted; its name and the reason stay so the conversation shows what happened.",
            ],
            [
              "Signed-in devices",
              "For each place you are signed in: the browser and system (such as Chrome on Windows) and when it was last used, so you can sign it out from Settings. Not your IP address.",
            ],
            [
              "Notifications",
              "Which mentions, direct messages and assigned issues you have been told about, and whether they were emailed.",
            ],
            [
              "Security records",
              "A count of failed sign-ins and any lockout on your account, and an audit log of changes to workspaces, members, roles, projects and issues.",
            ],
            [
              "Signing in with Google",
              "If you choose Continue with Google: Google's id for your account, your email address and your name. Not your Google password, and nothing else from your Google account.",
            ],
            ["Contact form", "Your name, email address and message, so we can reply."],
          ]}
        />
        <p>
          While you are signed in, whether you are online and when you are typing are held in memory
          for a few seconds and are never written to the database.
        </p>
      </>
    ),
  },
  {
    id: "what-we-do-not",
    title: "What we don't collect",
    body: (
      <Points
        items={[
          "No analytics, tracking pixels or advertising tools.",
          "No fonts, scripts or images loaded from other companies, apart from Google reCAPTCHA on the forms listed below.",
          "We don't read your messages to profile you, and we don't sell or rent any data.",
        ]}
      />
    ),
  },
  {
    id: "cookies",
    title: "Cookies and browser storage",
    body: (
      <>
        <Table
          head={["Name", "Why"]}
          rows={[
            [
              <code key="s">sessionid</code>,
              "Keeps you signed in. It can't be read by scripts on the page and, on the live site, is only sent over HTTPS. Lasts two weeks, or until you sign out.",
            ],
            [
              <code key="c">csrftoken</code>,
              "Proves that a form was sent from Baithak and not from another site.",
            ],
            [
              "Last workspace",
              "Saved in your browser (not a cookie) so Baithak can open the workspace you used last.",
            ],
            [
              "Next page",
              "Saved for one tab only, so you land back on an invitation after signing in.",
            ],
          ]}
        />
        <p>
          The sign-in, sign-up, password reset and contact pages load Google reCAPTCHA, which sets
          its own cookies. Only those pages load it.
        </p>
      </>
    ),
  },
  {
    id: "who-else-sees-it",
    title: "Who else sees it",
    body: (
      <>
        <p>
          <strong className="text-text">People in your workspace</strong> see what you post in the
          channels they can read. Private channels and direct messages are seen only by the people
          in them; being a workspace admin or owner does not open them. Admins can read the
          workspace&rsquo;s audit log.
        </p>
        <p>
          <strong className="text-text">Google reCAPTCHA</strong> checks that forms are sent by
          people. Google receives details about your browser and device and your IP address, under
          Google&rsquo;s <Out href="https://policies.google.com/privacy">Privacy Policy</Out> and{" "}
          <Out href="https://policies.google.com/terms">Terms of Service</Out>.
        </p>
        <p>
          <strong className="text-text">
            <Out href="https://resend.com/legal/privacy-policy">Resend</Out>
          </strong>{" "}
          delivers our emails (address confirmation, reset codes, notification emails and contact
          form messages), so it handles your email address and the message.
        </p>
        <p>
          <strong className="text-text">Google sign-in</strong>, if you use it, tells Google you are
          signing in to Baithak, under the same Google policies as above.
        </p>
        <p>
          <strong className="text-text">GitHub and other tools</strong> can post into a channel when
          a workspace admin connects them. Baithak receives what they send; it does not send your
          messages to them.
        </p>
        <p>We share data with anyone else only when the law requires it.</p>
      </>
    ),
  },
  {
    id: "how-it-is-protected",
    title: "How it is protected",
    body: (
      <>
        <Points
          items={[
            "The live site is served only over HTTPS, and browsers are told never to use plain HTTP.",
            "Passwords are hashed with Argon2id. Repeated wrong passwords or codes lock the account for longer each time.",
            "You can turn on two-step sign-in, so a code from an app on your phone is needed as well as your password.",
            "Forms are protected against cross-site requests and automated sign-ups. Signing in, signing up, posting, uploading, searching and the contact form are rate limited.",
            "Every request checks that you may see what you ask for. Something you can't see answers as if it does not exist.",
            "Files are checked by their content, not their name, and scanned for viruses before anyone can open them. A file that fails is deleted.",
            "Stored files are encrypted with AES-256, kept away from the public web folder, and opened only through links that expire after 12 hours and check your access again.",
            "Changes to workspaces, members and roles are written to an audit log.",
          ]}
        />
        <p>
          Before Baithak launches we are adding encryption of the stored database, including
          messages. This page will say so once it is live.
        </p>
      </>
    ),
  },
  {
    id: "how-long",
    title: "How long we keep it",
    body: (
      <Table
        head={["What", "For how long"]}
        rows={[
          ["Your account", "Until you delete it."],
          [
            "Messages, files and issues",
            "Until you, a workspace admin or the workspace owner deletes them. A deleted message loses its text and files at once; an empty row stays so threads and counts still add up.",
          ],
          ["Invitations", "7 days."],
          ["Password reset codes", "10 minutes."],
          ["Email confirmation links", "1 day."],
          [
            "Sign-in sessions and devices",
            "2 weeks, or until you or a device you trust signs them out.",
          ],
          ["Webhook delivery logs", "30 days."],
          ["Contact form messages", "Until the conversation is over; ask and we delete them."],
        ]}
      />
    ),
  },
  {
    id: "deleting-your-account",
    title: "Deleting your account",
    body: (
      <>
        <p>
          You can delete your account yourself, under Settings in any workspace, by confirming your
          password. Your account, sign-in, settings, reactions and notifications are removed for
          good, and you leave every workspace.
        </p>
        <p>
          Messages, files and issues you posted in workspaces shared with others stay there, shown
          as from a deleted account, so the conversations around them still make sense. Workspaces
          where you are the only member are deleted with everything in them. If you are the last
          owner of a workspace that has other people, make someone else an owner first.
        </p>
      </>
    ),
  },
  {
    id: "your-rights",
    title: "Your rights and choices",
    body: (
      <>
        <Points
          items={[
            "Ask for a copy of the data we hold about you.",
            "Ask us to correct something that is wrong.",
            "Ask us to remove something you posted, or your whole account.",
            "Turn off email notifications, or hold them during quiet hours, in your settings.",
          ]}
        />
        <p>
          Write to <Support /> from the address on your account. We reply within two weeks. What
          others post in a workspace belongs to that workspace, so for their messages we may point
          you to its admins.
        </p>
      </>
    ),
  },
  {
    id: "children",
    title: "Children",
    body: <p>Baithak is made for teams at work and is not meant for children under 16.</p>,
  },
  {
    id: "changes",
    title: "Changes to this page",
    body: (
      <p>
        When what we keep or who sees it changes, this page changes first, and the date at the top
        says when.
      </p>
    ),
  },
];

export function Privacy() {
  return (
    <DocLayout
      title="Privacy"
      intro="What Baithak keeps, who else sees it, how it is protected and how to have it removed."
      updated="23 November 2026"
      trail={[{ label: "Baithak", to: "/" }, { label: "Privacy" }]}
      sections={SECTIONS}
    />
  );
}
