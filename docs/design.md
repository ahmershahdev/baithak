# Design

Visual decisions for the web app. Tokens live in
[frontend/src/styles/tokens.css](../frontend/src/styles/tokens.css); this file says why they are
what they are. Change both in the same PR.

## Direction

A baithak is the sitting room where guests are received. The interface should feel like that
room: warm paper, deep ink, a few strong spice colors used with restraint. The canvas is beige,
never white; dark mode is warm charcoal, never black. Red is the brand and the action color, so it
appears on one thing per view (the primary button, the unread badge), not as decoration.

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
| `presence-*` | online emerald, away mustard, busy garnet, offline sand | same hues, lighter steps |

The primary button keeps tomato-700 with white text in both themes: a lighter red in dark mode
would need dark text, which reads as a different brand.

## Theme switching

`color-scheme: light dark` on `:root` follows the system. Setting `data-theme="light"` or
`data-theme="dark"` on `<html>` overrides it; the person's choice is stored in their profile and
applied before first paint. `light-dark()` needs Chrome 123, Firefox 120, Safari 17.5 (all 2024),
which is the browser floor for Baithak.

## Contrast

`node frontend/scripts/check-contrast.mjs` checks every text pair at 4.5:1 and every UI part
(borders on inputs, focus rings, presence dots) at 3:1, in both themes, and exits non-zero on a
failure. It goes into the `frontend` CI job in M1. Any new color pair a component uses is added to
the script's list first.

## Still to decide

- Typefaces: one display face and one text face, both with tabular figures.
- Spacing, radius and type scale tokens.
- Motion: durations and easing, with `prefers-reduced-motion` respected.
