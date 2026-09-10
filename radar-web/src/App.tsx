import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, NavLink, Outlet, Route, Routes, useNavigate } from "react-router-dom";
import { LogOut, Loader2 } from "lucide-react";
import { Toaster } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import Radar from "@/pages/Radar";
import Discovery from "@/pages/Discovery";
import Auth from "@/pages/Auth";
import NotFound from "@/pages/NotFound";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 60_000, refetchOnWindowFocus: false, retry: 1 },
  },
});

function Protegido() {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }
  if (!user) return <Navigate to="/auth" replace />;
  return <Outlet />;
}

// Casca própria do radar — sem o menu de conteúdo. Só a marca e o sair.
function Casca() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  return (
    <div className="min-h-screen bg-background">
      <header className="flex items-center justify-between border-b px-6 py-3">
        <div className="flex items-center gap-6">
          <span className="font-bold">📡 Radar de Pautas</span>
          <nav className="flex items-center gap-1 text-sm">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                `rounded-md px-3 py-1.5 ${isActive ? "bg-muted font-medium" : "text-muted-foreground hover:text-foreground"}`
              }
            >
              Radar
            </NavLink>
            <NavLink
              to="/discovery"
              className={({ isActive }) =>
                `rounded-md px-3 py-1.5 ${isActive ? "bg-muted font-medium" : "text-muted-foreground hover:text-foreground"}`
              }
            >
              Discovery
            </NavLink>
          </nav>
        </div>
        <div className="flex items-center gap-3 text-sm text-muted-foreground">
          {user?.email && <span className="hidden sm:inline">{user.email}</span>}
          <Button
            variant="ghost"
            size="sm"
            onClick={async () => {
              await signOut();
              navigate("/auth");
            }}
          >
            <LogOut className="mr-1 h-4 w-4" /> Sair
          </Button>
        </div>
      </header>
      <Outlet />
    </div>
  );
}

const App = () => (
  <QueryClientProvider client={queryClient}>
    <Toaster />
    <BrowserRouter>
      <Routes>
        <Route path="/auth" element={<Auth />} />
        <Route element={<Protegido />}>
          <Route element={<Casca />}>
            <Route path="/" element={<Radar />} />
            <Route path="/discovery" element={<Discovery />} />
          </Route>
        </Route>
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  </QueryClientProvider>
);

export default App;
