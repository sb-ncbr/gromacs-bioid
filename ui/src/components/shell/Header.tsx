import { Link, useLocation } from "react-router-dom";
import { BookOpen, Braces, Mail, Plug } from "lucide-react";

/** Served next to the app: the mkdocs site (/documentation/), the API's
 * Swagger page (/docs) and the MCP server's guide. */
const LINKS = [
  { href: "/documentation/", label: "Documentation", icon: BookOpen },
  { href: "/docs", label: "API", icon: Braces },
  { href: "/documentation/mcp/", label: "MCP server", icon: Plug },
];

const REPOSITORY = "https://github.com/sb-ncbr/gromacs-bioid";

/** The GitHub mark (lucide has no brand icons). */
function GitHubMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden>
      <path d="M12 .3a12 12 0 0 0-3.8 23.38c.6.12.83-.26.83-.57L9 21.07c-3.34.72-4.04-1.61-4.04-1.61-.55-1.39-1.34-1.76-1.34-1.76-1.08-.74.09-.73.09-.73 1.2.09 1.83 1.24 1.83 1.24 1.07 1.83 2.81 1.3 3.5 1 .1-.78.42-1.31.76-1.61-2.67-.3-5.47-1.33-5.47-5.93 0-1.31.47-2.38 1.24-3.22-.14-.3-.54-1.52.1-3.18 0 0 1-.32 3.3 1.23a11.5 11.5 0 0 1 6 0c2.28-1.55 3.29-1.23 3.29-1.23.64 1.66.24 2.88.12 3.18a4.65 4.65 0 0 1 1.23 3.22c0 4.61-2.8 5.63-5.48 5.92.42.36.81 1.1.81 2.22l-.01 3.29c0 .31.2.69.82.57A12 12 0 0 0 12 .3" />
    </svg>
  );
}

export default function Header() {
  // The brand is the page heading only on the front page; on a run page the
  // run name is the one h1.
  const home = useLocation().pathname === "/";
  const Brand = home ? "h1" : "p";
  return (
    <header className="flex flex-col gap-3 border-b border-base-200 pt-8 pb-6 mb-8 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
      <div>
        <Link to="/" className="no-underline">
          <Brand className="text-3xl font-bold text-text-heading sm:text-4xl">
            Molecular Dynamics <span className="text-primary">Bio</span>ID
          </Brand>
        </Link>
        <p className="mt-2 text-base text-text-muted">
          Automatic identification of biomolecules in molecular dynamics simulations
        </p>
      </div>
      <nav aria-label="Resources" className="-ml-2.5 flex flex-wrap items-center gap-1 sm:mt-2 sm:ml-0 sm:justify-end">
        {LINKS.map(({ href, label, icon: Icon }) => (
          <a
            key={href}
            href={href}
            className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-2 text-sm font-medium text-text-muted no-underline transition-colors hover:text-primary"
          >
            <Icon className="h-4 w-4" aria-hidden />
            {label}
          </a>
        ))}
        <a
          href={REPOSITORY}
          title="Source code on GitHub"
          aria-label="Source code on GitHub"
          className="inline-flex items-center justify-center rounded-lg p-2 text-text-muted transition-colors hover:text-primary"
        >
          <GitHubMark className="h-6 w-6" />
        </a>
        <a
          href="mailto:tomas.pavlik@muni.cz"
          title="Contact us"
          aria-label="Contact us by email"
          className="inline-flex items-center justify-center rounded-lg p-2 text-text-muted transition-colors hover:text-primary"
        >
          <Mail className="h-6 w-6" aria-hidden />
        </a>
      </nav>
    </header>
  );
}
