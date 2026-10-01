import { Outlet } from "react-router-dom";
import Header from "./Header";
import Footer from "./Footer";

export default function Layout() {
  return (
    <div className="flex min-h-screen flex-col bg-background text-text">
      <div className="mx-auto w-full max-w-7xl flex-1 px-4 sm:px-6 lg:px-8">
        <Header />
        <main className="pb-12">
          <Outlet />
        </main>
      </div>
      <Footer />
    </div>
  );
}
