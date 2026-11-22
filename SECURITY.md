# Security policy

## Supported versions

Baithak is in pre-release (`v0.x`) until `v1.0.0` at launch. Security fixes go to `main` and
into the next release; older pre-releases are not patched.

| Version | Supported |
|---|---|
| `main` | Yes |
| Latest `v0.x` pre-release | Yes, through the next release |
| Older pre-releases | No |

## Reporting a vulnerability

Please don't open a public issue, pull request or discussion for a security problem. Report it
privately:

1. **GitHub (preferred):** open the
   [Security tab](https://github.com/ahmershahdev/baithak/security/advisories/new) of this
   repository and choose **Report a vulnerability**.
2. **Email:** [support@ahmershah.dev](mailto:support@ahmershah.dev) with "Security" in the
   subject.

Include:

- the affected endpoint, WebSocket event, page or file
- steps to reproduce, with the role of each account involved (owner, admin, member, guest,
  outsider)
- what an attacker could read or change with it

## What happens next

| Step | When |
|---|---|
| First answer | Within 7 days |
| Our assessment and a plan | Within 14 days |
| Fix released | As soon as it is ready; you are told before it is public |

We credit reporters in the release notes and the advisory unless you ask us not to.

## What counts most

Problems that let someone read a private channel, a direct message, a file or another
workspace's data are treated as the most serious. So are ways around sign-in, the lockout
ladder, webhook signature checks or signed file links.

## In scope

- The code in this repository: the Django API and WebSocket consumers, Celery tasks, and the
  React web app.
- The live site at `baithak.ahmershah.dev` once it launches.

## Out of scope

- Reports from automated scanners with no working example.
- Missing security headers on pages that hold no data, or best-practice notes with no attack.
- Denial of service by sheer volume, and social engineering.
- Problems in third-party services (Google reCAPTCHA, Resend, GitHub) themselves; report those
  to the vendor.

## Testing

Test only against your own local copy (`npm run dev`, see the [README](README.md)) or accounts
you own. Don't access, change or delete other people's data, and stop as soon as you have shown
the problem. Good-faith research that follows this policy will not be pursued.

## How Baithak is protected

For context when looking for problems; details are in
[docs/architecture.md](docs/architecture.md).

- Passwords hashed with Argon2id; per-account lockout ladder; reCAPTCHA and a honeypot on
  anonymous forms; CSRF checks on every request, signed in or not.
- One access check in `backend/apps/core` decides who can read a channel, and the API,
  WebSockets, search and notifications all use it. Anything a person can't see answers `404`,
  and an access test calls every workspace endpoint as an outsider.
- Uploads are checked by content and size, stored outside anything the web server serves, and
  downloaded only through signed links that expire after 12 hours.
- GitHub webhooks are verified by signature before the payload is read; incoming webhook URLs
  are stored only as SHA-256 hashes.
- A Content Security Policy on the web app, `no-store` on API responses, and secrets only from
  environment variables.
