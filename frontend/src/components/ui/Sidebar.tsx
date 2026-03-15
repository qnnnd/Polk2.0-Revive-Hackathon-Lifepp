"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

const NAV_ITEMS = [
  { icon: "◫", label: "Dashboard", href: "/dashboard" },
  { icon: "✦", label: "AgentChat", href: "/dashboard?tab=agents" },
  { icon: "◎", label: "MemoryViewer", href: "/dashboard?tab=memory" },
  { icon: "◉", label: "Marketplace", href: "/marketplace" },
  { icon: "⬡", label: "NetworkGraph", href: "/network" },
];

export function Sidebar() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const tab = searchParams.get("tab");

  const isActive = (href: string) => {
    if (href === "/dashboard" && pathname === "/dashboard" && !tab) return true;
    if (href === "/dashboard?tab=agents" && pathname === "/dashboard" && tab === "agents") return true;
    if (href === "/dashboard?tab=memory" && pathname === "/dashboard" && tab === "memory") return true;
    if (href === "/marketplace" && pathname === "/marketplace") return true;
    if (href === "/network" && pathname === "/network") return true;
    if (pathname?.startsWith("/agents") && href === "/dashboard?tab=agents") return true;
    return false;
  };

  return (
    <aside className="sidebar">
      <div className="brand">
        <h1>Life++</h1>
        <p>Peer-to-Peer Cognitive Agent Network</p>
        <div className="seed-badge">
          <span className="dot" />
          Revive Seed Node
        </div>
      </div>

      <nav>
        {NAV_ITEMS.map((item) => (
          <Link
            key={item.label}
            href={item.href}
            className={`nav-btn ${isActive(item.href) ? "active" : ""}`}
          >
            <span className="icon">{item.icon}</span>
            {item.label}
          </Link>
        ))}
      </nav>

      <div className="sidebar-footer">
        Life++ v0.1 — Testnet<br />
        Persistent Agent + Memory<br />
        On-chain Settlement (Revive)
      </div>
    </aside>
  );
}
