import { Link, useLocation } from "react-router-dom";
import { BookOpen, Braces, Mail, Plug } from "lucide-react";

/** Served next to the app: the mkdocs site (/documentation/), the API's
 * Swagger page (/docs) and the MCP server's guide. */
const LINKS = [
  { href: "/documentation/", label: "Documentation", icon: BookOpen },
  { href: "/docs", label: "API", icon: Braces },
  { href: "/documentation/mcp/", label: "MCP server", icon: Plug },
];

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
