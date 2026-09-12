import { useQuery } from "@tanstack/react-query";
import { Navigate, Route, Routes } from "react-router-dom";

import Shell from "./components/Shell";
import { Page } from "./components/motion";
import { api } from "./lib/api";
import Budgets from "./pages/Budgets";
import Contacts from "./pages/Contacts";
import Dashboard from "./pages/Dashboard";
import Debts from "./pages/Debts";
import ImportPage from "./pages/ImportPage";
import Insights from "./pages/Insights";
import Links from "./pages/Links";
import LoanDetail from "./pages/LoanDetail";
import Loans from "./pages/Loans";
import Login from "./pages/Login";
import Market from "./pages/Market";
import Review from "./pages/Review";
import Settings from "./pages/Settings";
import Transactions from "./pages/Transactions";
import Wishlist from "./pages/Wishlist";

const ROUTES = [
  { path: "/", element: <Dashboard /> },
  { path: "/import", element: <ImportPage /> },
  { path: "/transactions", element: <Transactions /> },
  { path: "/review", element: <Review /> },
  { path: "/contacts", element: <Contacts /> },
  { path: "/debts", element: <Debts /> },
  { path: "/links", element: <Links /> },
  { path: "/market", element: <Market /> },
  { path: "/insights", element: <Insights /> },
  { path: "/wishlist", element: <Wishlist /> },
  { path: "/budgets", element: <Budgets /> },
  { path: "/loans", element: <Loans /> },
  { path: "/loans/:id", element: <LoanDetail /> },
  { path: "/settings", element: <Settings /> },
];

export default function App() {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<{ user: string }>("/api/auth/me"),
    retry: false,
  });

  if (isLoading) {
    return (
      <div className="grid min-h-screen place-items-center bg-bg text-text-mute">
        در حال بارگذاری…
      </div>
    );
  }

  if (!data) return <Login onSuccess={() => refetch()} />;

  return (
    <Shell>
      <Routes>
        {ROUTES.map(({ path, element }) => (
          <Route key={path} path={path} element={<Page>{element}</Page>} />
        ))}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Shell>
  );
}
