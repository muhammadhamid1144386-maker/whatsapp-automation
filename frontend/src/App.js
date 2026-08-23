import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import Orders from "@/pages/Orders";
import OrderDetail from "@/pages/OrderDetail";
import Customers from "@/pages/Customers";
import MenuPage from "@/pages/MenuPage";
import Conversations from "@/pages/Conversations";
import WhatsAppPage from "@/pages/WhatsAppPage";
import GoogleSheets from "@/pages/GoogleSheets";
import Analytics from "@/pages/Analytics";
import SettingsPage from "@/pages/Settings";
import ChatDemo from "@/pages/ChatDemo";

const Protected = ({ children }) => {
  const { user, loading } = useAuth();
  if (loading)
    return (
      <div className="grid min-h-screen place-items-center bg-background">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  if (!user) return <Navigate to="/login" replace />;
  return children;
};

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/chat" element={<ChatDemo />} />
          <Route path="/dashboard" element={<Protected><Dashboard /></Protected>} />
          <Route path="/orders" element={<Protected><Orders /></Protected>} />
          <Route path="/orders/:id" element={<Protected><OrderDetail /></Protected>} />
          <Route path="/customers" element={<Protected><Customers /></Protected>} />
          <Route path="/menu" element={<Protected><MenuPage /></Protected>} />
          <Route path="/conversations" element={<Protected><Conversations /></Protected>} />
          <Route path="/whatsapp" element={<Protected><WhatsAppPage /></Protected>} />
          <Route path="/google-sheets" element={<Protected><GoogleSheets /></Protected>} />
          <Route path="/analytics" element={<Protected><Analytics /></Protected>} />
          <Route path="/settings" element={<Protected><SettingsPage /></Protected>} />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
        <Toaster position="top-right" richColors closeButton />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
