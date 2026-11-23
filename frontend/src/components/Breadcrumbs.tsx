import { Link } from "react-router";

export interface Crumb {
  label: string;
  to?: string;
}

export function Breadcrumbs({ trail }: { trail: Crumb[] }) {
  return (
    <nav aria-label="Breadcrumb">
      <ol className="flex flex-wrap items-center gap-1.5 text-sm text-text-subtle">
        {trail.map((crumb, index) => {
          const last = index === trail.length - 1;
          return (
            <li key={crumb.label} className="flex items-center gap-1.5">
              {crumb.to && !last ? (
                <Link
                  to={crumb.to}
                  className="rounded-md font-medium text-text-muted transition-colors hover:text-text focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:outline-none"
                >
                  {crumb.label}
                </Link>
              ) : (
                <span aria-current={last ? "page" : undefined} className="font-semibold text-text">
                  {crumb.label}
                </span>
              )}
              {!last && (
                <svg viewBox="0 0 16 16" className="size-3.5" aria-hidden="true">
                  <path
                    d="M6 3.5 10.5 8 6 12.5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.6"
                  />
                </svg>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
