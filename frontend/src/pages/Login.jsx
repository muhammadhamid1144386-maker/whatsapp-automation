import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { ChefHat, Loader2, MessageCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/context/AuthContext";

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("owner@pizzapalace.pk");
  const [password, setPassword] = useState("Pizza123!");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/dashboard" replace />;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    const result = await login(email, password);
    setBusy(false);
    if (result.ok) navigate("/dashboard");
    else setError(result.error);
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      <div className="relative hidden overflow-hidden bg-[#1A1817] p-12 text-stone-100 lg:flex lg:flex-col lg:justify-between">
        <img
          src="https://images.pexels.com/photos/12203611/pexels-photo-12203611.jpeg"
          alt="Restaurant kitchen"
          className="absolute inset-0 h-full w-full object-cover opacity-30"
        />
        <div className="relative">
          <span className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/5 px-3 py-1 text-xs font-medium uppercase tracking-widest">
            <ChefHat className="h-3.5 w-3.5" /> AI Restaurant Assistant
          </span>
        </div>
        <div className="relative max-w-lg">
          <h2 className="font-display text-4xl font-black leading-[1.05] lg:text-5xl">
            Your 24/7 WhatsApp
            <br />
            order taker.
          </h2>
          <p className="mt-5 text-base text-stone-300">
            The AI greets customers, reads Urdu, Roman Urdu and English, builds the cart, calculates the bill
            and drops the order on your screen the second it is confirmed.
          </p>
          <div className="mt-8 flex flex-wrap gap-2 text-xs">
            {["Live order board", "Menu control", "Customer history", "Sheets export"].map((t) => (
              <span key={t} className="rounded-full border border-white/15 bg-white/5 px-3 py-1">
                {t}
              </span>
            ))}
          </div>
        </div>
        <p className="relative text-xs text-stone-400">Built for restaurants in Pakistan · PKR</p>
      </div>

      <div className="flex items-center justify-center p-6 sm:p-12">
        <div className="w-full max-w-sm">
          <span className="grid h-11 w-11 place-items-center rounded-xl bg-primary text-primary-foreground">
            <ChefHat className="h-5 w-5" />
          </span>
          <h1 className="mt-6 font-display text-3xl font-bold">Restaurant login</h1>
          <p className="mt-1.5 text-sm text-muted-foreground">
            Sign in to manage live orders and your AI assistant.
          </p>

          <form onSubmit={submit} className="mt-8 space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                data-testid="login-email-input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                data-testid="login-password-input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
            </div>
            {error && (
              <p data-testid="login-error" className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {error}
              </p>
            )}
            <Button type="submit" disabled={busy} data-testid="login-submit-btn" className="h-11 w-full rounded-full">
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : "Sign in"}
            </Button>
          </form>

          <div className="mt-6 rounded-xl border bg-muted/40 p-4 text-xs">
            <p className="font-semibold">Demo account</p>
            <p className="mt-1 font-mono-plex text-muted-foreground">owner@pizzapalace.pk · Pizza123!</p>
          </div>

          <Link
            to="/chat"
            data-testid="login-open-chat-link"
            className="mt-4 flex items-center justify-center gap-2 text-sm font-medium text-primary transition-colors hover:underline"
          >
            <MessageCircle className="h-4 w-4" /> Or try the customer chat demo
          </Link>
        </div>
      </div>
    </div>
  );
}
