import type { ReactNode } from "react";
import { Link } from "react-router";

import { SITE_URL, SUPPORT_EMAIL } from "../contact";
import { Breadcrumbs, type Crumb } from "./Breadcrumbs";
import { Jaali, Wordmark } from "./brand";

export interface DocSection {
  id: string;
  title: string;
  body: ReactNode;
}

/** A long page to read, such as the privacy policy, with a table of contents beside it. */
export function DocLayout({
  title,
  intro,
  updated,
  trail,
  sections,
}: {
  title: string;
  intro: ReactNode;
  updated: string;
  trail: Crumb[];
  sections: DocSection[];
}) {
  return (
    <div className="min-h-dvh bg-bg">
      <header className="relative overflow-hidden border-b border-border bg-bg-subtle">
        <Jaali />
        <div className="relative mx-auto flex max-w-6xl flex-col gap-8 px-5 pt-6 pb-12 sm:px-10">
          <div className="flex items-center justify-between gap-4">
            <Link
              to="/"
              className="rounded-md focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:outline-none"
            >
              <Wordmark />
              <span className="sr-only">Baithak home</span>
            </Link>
            <Link
              to="/contact"
              className="rounded-xl border border-border-strong bg-surface px-4 py-1.5 text-sm font-semibold transition-colors hover:border-text-subtle"
            >
              Contact us
            </Link>
          </div>
          <div className="settle flex max-w-3xl flex-col gap-4">
            <Breadcrumbs trail={trail} />
            <h1 className="wonky font-display text-4xl font-semibold tracking-tight sm:text-5xl">
              {title}
            </h1>
            <p className="text-lg text-text-muted">{intro}</p>
            <p className="text-sm text-text-subtle">Last updated {updated}</p>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-6xl gap-10 px-5 py-12 sm:px-10 lg:grid-cols-[14rem_minmax(0,1fr)] lg:gap-16">
        <nav aria-label="On this page" className="lg:sticky lg:top-8 lg:self-start">
          <p className="mb-3 text-xs font-semibold tracking-wide text-text-subtle uppercase">
            On this page
          </p>
          <ol className="flex flex-col gap-1 border-l border-border text-sm">
            {sections.map((section) => (
              <li key={section.id}>
                <a
                  href={`#${section.id}`}
                  className="-ml-px block border-l-2 border-transparent py-1 pl-3 text-text-muted transition-colors hover:border-accent hover:text-text"
                >
                  {section.title}
                </a>
              </li>
            ))}
          </ol>
        </nav>

        <article className="flex max-w-3xl flex-col gap-12">
          {sections.map((section) => (
            <section key={section.id} id={section.id} className="scroll-mt-8">
              <h2 className="wonky mb-4 font-display text-2xl font-semibold tracking-tight">
                <a href={`#${section.id}`} className="hover:text-accent-text">
                  {section.title}
                </a>
              </h2>
              <div className="flex flex-col gap-4 leading-relaxed text-text-muted">
                {section.body}
              </div>
            </section>
          ))}
        </article>
      </div>

      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-6xl flex-wrap gap-x-5 gap-y-1 px-5 py-6 text-sm text-text-subtle sm:px-10">
          <Link to="/contact" className="hover:text-text">
            Contact
          </Link>
          <Link to="/privacy" className="hover:text-text">
            Privacy
          </Link>
          <a href={`mailto:${SUPPORT_EMAIL}`} className="hover:text-text">
            {SUPPORT_EMAIL}
          </a>
          <a href={SITE_URL} target="_blank" rel="noreferrer" className="hover:text-text">
            ahmershah.dev
          </a>
        </div>
      </footer>
    </div>
  );
}
