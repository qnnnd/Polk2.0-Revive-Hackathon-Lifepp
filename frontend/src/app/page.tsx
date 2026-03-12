"use client";

import { useState, useEffect } from "react";
import { authApi, setAccessToken, getAccessToken } from "@/lib/api";
import { toast } from "sonner";

export default function Home() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [username, setUsername] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (getAccessToken()) setIsLoggedIn(true);
  }, []);

  const handleRegisterAndLogin = async () => {
    if (!username.trim()) return;
    setLoading(true);
    try {
      const did = `did:key:${crypto.randomUUID()}`;
      await authApi.register({
        did,
        username: username.trim(),
        display_name: username.trim(),
      });
      const tokenRes = await authApi.login(username.trim());
      setAccessToken(tokenRes.access_token);
      setIsLoggedIn(true);
      toast.success("Welcome to Life++!");
    } catch (err: any) {
      if (err.status === 409) {
        try {
          const tokenRes = await authApi.login(username.trim());
          setAccessToken(tokenRes.access_token);
          setIsLoggedIn(true);
          toast.success(`Welcome back, ${username}!`);
        } catch {
          toast.error("Login failed");
        }
      } else {
        toast.error(err.message ?? "Registration failed");
      }
    } finally {
      setLoading(false);
    }
  };

  if (!isLoggedIn) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="bg-surface2 rounded-2xl border border-border p-8 w-full max-w-md space-y-6">
          <div className="text-center space-y-2">
            <h1 className="text-3xl font-bold font-syne bg-gradient-to-r from-accent to-accent2 bg-clip-text text-transparent">
              Life++
            </h1>
            <p className="text-sm text-muted">Peer-to-Peer Cognitive Agent Network</p>
          </div>
          <div className="space-y-4">
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleRegisterAndLogin()}
              placeholder="Choose a username"
              className="w-full bg-surface3 border border-border rounded-xl px-4 py-3 text-sm placeholder:text-muted outline-none focus:border-accent/50 transition-colors"
            />
            <button
              onClick={handleRegisterAndLogin}
              disabled={loading || !username.trim()}
              className="w-full bg-accent hover:bg-accent/80 disabled:opacity-50 text-white rounded-xl py-3 text-sm font-semibold transition-all"
            >
              {loading ? "Connecting..." : "Enter Life++"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-border px-6 py-4 flex items-center justify-between">
        <h1 className="text-xl font-bold font-syne bg-gradient-to-r from-accent to-accent2 bg-clip-text text-transparent">
          Life++
        </h1>
        <button
          onClick={() => {
            setAccessToken(null);
            setIsLoggedIn(false);
          }}
          className="text-xs text-muted hover:text-foreground transition-colors"
        >
          Logout
        </button>
      </header>
      <main className="p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <DashboardCard
            title="Agents"
            description="Create and manage your persistent AI agents"
            icon="🤖"
            href="/dashboard"
          />
          <DashboardCard
            title="Network"
            description="Explore the agent network graph"
            icon="🌐"
            href="/dashboard"
          />
          <DashboardCard
            title="Marketplace"
            description="Find tasks for your agents"
            icon="🏪"
            href="/dashboard"
          />
        </div>
      </main>
    </div>
  );
}

function DashboardCard({
  title,
  description,
  icon,
  href,
}: {
  title: string;
  description: string;
  icon: string;
  href: string;
}) {
  return (
    <a
      href={href}
      className="bg-surface2 rounded-2xl border border-border p-6 hover:border-accent/40 transition-all space-y-3"
    >
      <span className="text-3xl">{icon}</span>
      <h3 className="font-semibold font-syne">{title}</h3>
      <p className="text-sm text-muted">{description}</p>
    </a>
  );
}
