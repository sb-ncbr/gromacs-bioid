import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";
import Layout from "./components/shell/Layout";
import Frontpage from "./pages/Frontpage";
import NotFoundPage from "./pages/NotFoundPage";

// The run page carries Mol* (4.7 MB); the front page does not need it.
const RunResultsPage = lazy(() => import("./pages/RunResultsPage"));
// Operators only; not linked from the header.
const AdminPage = lazy(() => import("./pages/AdminPage"));

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Frontpage />} />
        <Route
          path="runs/:runId"
          element={
            <Suspense fallback={null}>
              <RunResultsPage />
            </Suspense>
          }
        />
        <Route
          path="admin"
          element={
            <Suspense fallback={null}>
              <AdminPage />
            </Suspense>
          }
        />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
