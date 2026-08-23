import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ChefHat, LogIn } from "lucide-react";
import { WhatsAppSimulator } from "@/components/WhatsAppSimulator";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function ChatDemo() {
  const [phone, setPhone] = useState(() => localStorage.getItem("ara_demo_phone") || "03001234567");

  useEffect(() => {
    localStorage.setItem("ara_demo_phone", phone);
  }, [phone]);

  return (
    <div className="min-h-screen bg-background">
      <header className="glass-header sticky top-0 z-20 flex h-16 items-center justify-between border-b px-4 sm:px-8">
        <Link to="/" className="flex items-center gap-2">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-primary text-primary-foreground">
            <ChefHat className="h-4 w-4" />
          </span>
          <span className="font-display text-base font-bold">AI Restaurant Assistant</span>
        </Link>
        <Link to="/login">
          <Button variant="outline" size="sm" className="rounded-full" data-testid="chat-login-btn">
            <LogIn className="mr-1.5 h-3.5 w-3.5" /> Owner login
          </Button>
        </Link>
      </header>

      <main className="mx-auto grid max-w-6xl gap-10 px-4 py-10 sm:px-8 lg:grid-cols-[1fr_380px] lg:py-16">
        <div>
          <span className="inline-flex items-center rounded-full border bg-card px-3 py-1 text-xs font-medium uppercase tracking-widest text-muted-foreground">
            Customer demo
          </span>
          <h1 className="mt-5 font-display text-4xl font-black leading-[1.05] sm:text-5xl lg:text-6xl">
            Order from Pizza Palace
            <br />
            <span className="text-primary">on WhatsApp.</span>
          </h1>
          <p className="mt-5 max-w-xl text-base text-muted-foreground">
            This is the customer side. Chat in English, Urdu or Roman Urdu. The assistant reads the real menu,
            builds a server-side cart, calculates your bill and places the order — and the restaurant's dashboard
            lights up the moment you confirm.
          </p>

          <div className="mt-8 max-w-xs space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Your phone number
            </label>
            <Input data-testid="chat-phone-input" value={phone} onChange={(e) => setPhone(e.target.value)} />
            <p className="text-xs text-muted-foreground">
              Change this to act as a different customer. Your history is remembered per number.
            </p>
          </div>

          <div className="mt-10 grid gap-4 sm:grid-cols-2">
            {[
              { t: "Try", d: "“Hi”" },
              { t: "Then", d: "“menu dikhayen”" },
              { t: "Order", d: "“1 zinger burger aur fries”" },
              { t: "Finish", d: "“delivery” → address → “confirm”" },
            ].map((s) => (
              <div key={s.t} className="card-surface p-5">
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{s.t}</p>
                <p className="mt-1.5 font-medium">{s.d}</p>
              </div>
            ))}
          </div>

          <p className="mt-8 max-w-xl text-xs text-muted-foreground">
            This simulator does not connect to any real WhatsApp account. In production the same code path runs
            behind a WhatsApp provider. The optional Baileys provider is an unofficial WhatsApp Web bridge and is
            not the official WhatsApp Business API.
          </p>
        </div>

        <div className="lg:sticky lg:top-24 lg:h-fit">
          <WhatsAppSimulator slug="pizza-palace" phone={phone} />
        </div>
      </main>
    </div>
  );
}
