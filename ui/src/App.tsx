import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";
import Layout from "./components/shell/Layout";
import Frontpage from "./pages/Frontpage";
import RunResultsPage from "./pages/RunResultsPage";

// Dev-only fixture playground. Gated so it is absent (and tree-shaken) from prod builds.
const DevPlayground = import.meta.env.DEV
  ? lazy(() => import("./dev/FixturesPlayground"))
  : null;

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Frontpage />} />
        <Route path="runs/:runId" element={<RunResultsPage />} />
        {DevPlayground && (
          <Route
            path="dev/results-demo"
            element={
              <Suspense fallback={<div>Loading…</div>}>
                <DevPlayground />
              </Suspense>
            }
          />
        )}
      </Route>
    </Routes>
  );
}
