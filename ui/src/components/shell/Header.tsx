import { Link, useLocation } from "react-router-dom";
import { Mail } from "lucide-react";

export default function Header() {
  // The brand is the page heading only on the front page; on a run page the
  // run name is the one h1.
  const home = useLocation().pathname === "/";
  const Brand = home ? "h1" : "p";
  return (
    <header className="flex items-start justify-between gap-4 border-b border-base-200 pt-8 pb-6 mb-8">
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
      <a
        href="mailto:tomas.pavlik@muni.cz"
        title="Contact us"
        aria-label="Contact us by email"
        className="mt-2 inline-flex items-center justify-center rounded-lg p-2 text-text-muted transition-colors hover:text-primary"
      >
        <Mail className="h-6 w-6" aria-hidden />
      </a>
    </header>
  );
}
