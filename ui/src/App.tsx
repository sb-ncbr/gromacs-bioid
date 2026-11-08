import { Route, Routes } from "react-router-dom";
import Layout from "./components/shell/Layout";
import Frontpage from "./pages/Frontpage";
import RunResultsPage from "./pages/RunResultsPage";
import NotFoundPage from "./pages/NotFoundPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Frontpage />} />
        <Route path="runs/:runId" element={<RunResultsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
