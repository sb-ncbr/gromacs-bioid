/** Any route the app does not know: say so and offer the way back. */
import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <div className="mx-auto max-w-2xl py-12 text-center">
      <h1 className="text-2xl font-bold text-text-heading">Page not found</h1>
      <p className="mt-2 text-text-muted">There is nothing at this address.</p>
      <Link to="/" className="mt-4 inline-block font-medium text-primary underline-offset-2 hover:underline">
        Go to the BioID start page
      </Link>
    </div>
  );
}
