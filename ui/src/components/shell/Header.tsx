import { Link } from "react-router-dom";
import { Mail } from "lucide-react";

export default function Header() {
  return (
    <header className="flex items-start justify-between gap-4 border-b border-base-200 pt-8 pb-6 mb-8">
      <div>
        <Link to="/" className="no-underline">
          <h1 className="text-3xl font-bold text-text-heading sm:text-4xl">
            Molecular Dynamics <span className="text-primary">Bio</span>ID
          </h1>
        </Link>
        <p className="mt-2 text-base text-text-muted">
          Automatic identification of biomolecules in molecular dynamics simulations
        </p>
      </div>
      <a
        href="mailto:tomas.pavlik@muni.cz"
        title="Contact us"
        className="mt-2 inline-flex items-center justify-center rounded-lg p-2 text-text-muted transition-colors hover:text-primary"
      >
        <Mail className="h-6 w-6" />
      </a>
    </header>
  );
}
