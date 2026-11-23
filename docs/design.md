# Design

Visual decisions for the web app. Tokens live in
[frontend/src/styles/tokens.css](../frontend/src/styles/tokens.css); this file says why they are
what they are. Change both in the same PR.

## Direction

A baithak is the sitting room where guests are received. The interface should feel like that
room: warm paper, deep ink, a few strong spice colors used with restraint. The canvas is beige,
never white; dark mode is warm charcoal, never black. Red is the brand and the action color, so it
appears on one thing per view (the primary button, the unread badge), not as decoration.

## Logo

`frontend/public/logo.svg` (4:3, 1200 x 900) is the mark above the wordmark. The mark is a
jharoka arch in tomato-700 with two people sitting side by side on a mustard gaddi, a diya
between them: a baithak is the room where people sit together and talk. The wordmark is
"baithak" in lowercase Fraunces at weight 640 with the soft and wonky axes on, turned into
outlines so it needs no font. The SVGs switch the arch and ink to their dark-theme values with
`prefers-color-scheme`.

| File | Use |
|---|---|
| `logo.svg`, `logo.png` | the full 4:3 logo (PNG on sand-50, for places that need a bitmap) |
| `logo-mark.svg` | the mark alone |
| `favicon.svg`, `favicon.ico` (16, 32, 48) | browser tabs; small sizes leave out the diya |
| `apple-touch-icon.png`, `icon-512.png` | home screens, mark on sand-50 |

All of them are built by `frontend/scripts/make-brand.py` (command at the top of the file).
Change the script, not the files.

## Type

Fraunces (variable, with the soft and wonky axes) for display text and the wordmark; Instrument
Sans (variable width) for everything else, with tabular figures on so counts and times line up.
Both are self-hosted from `@fontsource-variable`, so no request goes to a font service and the
CSP can stay `font-src 'self'`.

## Palette

| Ramp | Role | Anchor |
|---|---|---|
| Sand | Light theme neutrals: canvas, sidebar, borders, text | `sand-50` #FBF8F2, `sand-950` #1F1A15 |
| Kohl | Dark theme neutrals, warm charcoal | `kohl-900` #13110F, `kohl-50` #F3ECE0 |
| Tomato | Brand, primary action, unread, focus | `tomato-700` #C73A1E |
| Ember | Orange-red second accent: issues, illustration | `ember-500` #EE6214 |
| Mustard | Warning, mentions, away | `mustard-400` #E3B12C |
| Emerald | Success, online | `emerald-700` #146B4C |
| Garnet | Errors, destructive actions | `garnet-700` #AF1F3E |
| Neel | Information, links inside messages | `neel-700` #34539E |

Each ramp has steps 50 to 950 (Kohl also has 850). Garnet is a cooler, bluer red than Tomato on
purpose: if danger and brand were the same hue, every primary button would look like a delete.

The six hues (Tomato, Ember, Mustard, Emerald, Garnet, Neel) are also the avatar and channel
colors, picked from a hash of the id so a person keeps their color everywhere.

## Semantic tokens

Components never use a ramp step directly; they use the semantic tokens, which switch between
themes through `light-dark()`.

| Token | Light | Dark |
|---|---|---|
| `bg` / `bg-subtle` | sand-50 / sand-100 | kohl-900 / kohl-950 |
| `surface` / `surface-raised` / `surface-sunken` | #FFFCF7 / #FFFFFF / sand-200 | kohl-800 / kohl-700 / kohl-950 |
| `text` / `text-muted` / `text-subtle` | sand-950 / sand-700 / sand-600 | kohl-50 / kohl-200 / kohl-300 |
| `border` / `border-strong` | sand-200 / sand-500 | kohl-600 / kohl-400 |
| `accent` (fill) with `on-accent` | tomato-700, white | tomato-700, white |
| `accent-text` | tomato-800 | tomato-400 |
| `success` / `warning` / `danger` / `info` | emerald-700 / mustard-800 / garnet-700 / neel-700 | emerald-300 / mustard-300 / garnet-400 / neel-300 |
| `*-soft` with `*-soft-text` | 100 step, 800 text | 950 step, 200 text |
| `mention` / `mention-edge` | mustard-100 / mustard-400 | mustard-950 / mustard-500 |
| `selection` / `selection-text` | mustard-200 / sand-950 | mustard-800 / kohl-50 |
| `scrollbar-thumb` / `-hover` | sand-500 / tomato-600 | kohl-400 / tomato-500 |
| `presence-*` | online emerald, away mustard, busy garnet, offline sand | same hues, lighter steps |

The primary button keeps tomato-700 with white text in both themes: a lighter red in dark mode
would need dark text, which reads as a different brand.

## Theme switching

`color-scheme: light dark` on `:root` follows the system. Setting `data-theme="light"` or
`data-theme="dark"` on `<html>` overrides it; the tokens support this, but there is no theme
picker yet, so the system setting always decides. `light-dark()` needs Chrome 123, Firefox 120,
Safari 17.5 (all 2024), which is the browser floor for Baithak.

## Tailwind

`frontend/src/index.css` clears Tailwind's default palette and maps only the semantic tokens into
the theme (`bg-surface`, `text-text-muted`, `border-border`, `bg-presence-online`). Ramp steps are
not Tailwind colors, so a component can't reach past the themes.

## Forms

Inputs sit on `bg` inside `surface` cards: `border-strong` on `surface-raised` is 2.95:1 in dark,
under the 3:1 UI minimum, while on `bg` it passes in both themes. Field errors use `danger` text
and are tied to the input with `aria-describedby` and `aria-invalid`.

Destructive actions take two steps. The first is a quiet outlined button with `danger` text
("Delete account"); the confirming one is a solid `danger-fill` button with `on-danger` text and
words that say what is lost ("Delete my account for good"), next to Cancel. The brand red never
marks a destructive action.

Dropdowns use `components/Select.tsx`, never a native `select`: the open list of a native select
is drawn by the browser and the OS and ignores the theme. Its list is a `surface-raised` popover
like the workspace switcher, with the select-only combobox keyboard pattern, and it sends its
value with the form through a hidden input.

## Contrast

`npm run contrast` (`frontend/scripts/check-contrast.mjs`) checks every text pair at 4.5:1 and
every UI part (borders on inputs, focus rings, presence dots) at 3:1, in both themes, and exits
non-zero on a failure. It runs in the `frontend` CI job. Any new color pair a component uses is
added to the script's list first.

## Selection and scrollbars

Selected text is turmeric (mustard-200, mustard-800 in dark), like a highlighter on paper, so a
selection never reads as an error or as the brand red. Scrollbars are a slim pill floating in a
clear track, sand at rest and brand red under the pointer; the thumb meets 3:1 like any control.

## Sign-in screens

Wide screens split in two: on the left the brand room (sand, a faint jaali of eight-point stars,
the arch scene, "Pull up a cushion."), on the right the form. Narrow screens show the wordmark
and the form only. Headings are Fraunces with the soft and wonky axes (`.wonky`).

- **The scene**: the arch rises, the two people sit down one after the other, the diya flickers
  and glows, and short messages float up between them in turn.
- **Show password (parda)**: the eye sits in a small jharoka with two brand-red curtains. Hidden,
  the curtains are drawn; shown, they gather to the sides with mustard tie-backs and the eye
  glances across once.
- **Primary button (lamplight)**: a band of warm light passes across on hover, the arrow steps
  forward, the button gives a little when pressed. While waiting, the label becomes three dots
  rising in turn, like people taking turns to speak.
- **Password strength**: four segments under the new-password field, red, mustard, then green,
  with zxcvbn's advice in words. It scores against the email, handle and name typed so far.

## Workspace screens

A two-column grid from medium widths: a 17rem sidebar on `bg-subtle` (wordmark, workspace
switcher, role, search, notifications, channels, direct messages, workspace pages, then the
signed-in person with Settings and Sign out under their name), and the page on `bg`, at most
56rem wide. The sidebar is as tall as the window and scrolls; its parts never shrink to fit.
On narrow screens the sidebar sits on top and the account block moves below the page. A thread
opens beside the channel on wide screens and full screen on narrow ones.

A channel takes the whole page beside the sidebar, with no width cap, so long messages and code
blocks have room. Its header shows the channel's icon, name and topic, the members as a stack of
three avatars with a count, and a search button scoped to the channel. Messages are split by day
with a centered pill ("Today", "Yesterday", then the date). Pills don't stick to the top while
scrolling, since a stuck line crosses the message under it. Grouped messages show their time in the
avatar column on hover. Message actions are icon buttons in a raised bar at the top right, each
named for screen readers and given a tooltip. A floating pill takes the reader back to the
latest message, counting what arrived while they were scrolled up.

The composer has a formatting bar (bold, italic, strike, code, link, quote, list) that wraps or
unwraps the selection; Ctrl+B and Ctrl+I do the same. The text box grows with the draft up to
15rem. Icons are drawn in `components/icons.tsx` on a 20-unit grid with 1.6 strokes, so they
stay one family.

Formatted messages keep to the tokens: inline code and code blocks on `surface-sunken` in the
mono font, quotes behind a `border-strong` rule in `text-muted`, links in `info` (neel) with an
underline so they never look like the brand red, and spoilers as a solid `text` bar until
pressed. Headings in a message are Fraunces at `xl`, `lg` and `base` for `#`, `##` and `###`.

Messages from the same sender within five minutes are grouped under one name and avatar.
Messages with no author show as "Deleted account" and are never grouped, since two deleted
accounts look the same.

## Motion

All durations and easing live in `frontend/src/styles/motion.css`: `--ease-out` for things
arriving, `--ease-spring` for the people sitting and the arrow, `--ease-in-out` for loops. Under
`prefers-reduced-motion` every animation and transition is cut to 1 ms and the message loop
shows one message, still.

## Still to decide

- Spacing, radius and type scale tokens. Components use Tailwind's default spacing and radius
  steps for now.
- A theme picker (light, dark, system), stored per person.
