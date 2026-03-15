"use client";

import { useState, useEffect, useRef } from "react";
import { toast } from "sonner";
import { getAccessToken, setAccessToken } from "@/lib/api";
import { authApi } from "@/lib/api";

interface TopbarProps {
  title: string;
  description: string;
}

declare global {
  interface Window {
    ethereum?: {
      request: (args: { method: string; params?: unknown[] }) => Promise<string[]>;
    };
  }
}

export function Topbar({ title, description }: TopbarProps) {
  const [walletAddress, setWalletAddress] = useState<string | null>(null);
  const [username, setUsername] = useState<string | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [showWalletMenu, setShowWalletMenu] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const userMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      setUsername(null);
      setWalletAddress(null);
      return;
    }
    authApi
      .getMe()
      .then((user) => {
        setUsername(user.username ?? null);
        setWalletAddress(user.wallet_address ?? null);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!showUserMenu) return;
    const onOutside = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setShowUserMenu(false);
      }
    };
    document.addEventListener("click", onOutside);
    return () => document.removeEventListener("click", onOutside);
  }, [showUserMenu]);

  useEffect(() => {
    if (!showWalletMenu) return;
    const onOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowWalletMenu(false);
      }
    };
    document.addEventListener("click", onOutside);
    return () => document.removeEventListener("click", onOutside);
  }, [showWalletMenu]);

  const handleConnectWallet = async () => {
    if (walletAddress) {
      setShowWalletMenu((v) => !v);
      return;
    }
    if (typeof window === "undefined" || !window.ethereum) {
      toast.error("Please install MetaMask to connect a wallet.");
      return;
    }
    setConnecting(true);
    try {
      const accounts = await window.ethereum.request({ method: "eth_requestAccounts" });
      const address = accounts?.[0];
      if (!address) {
        toast.error("No account selected.");
        setConnecting(false);
        return;
      }
      await authApi.updateWallet(address);
      setWalletAddress(address);
      toast.success(`Connected: ${address.slice(0, 6)}...${address.slice(-4)}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to connect wallet";
      toast.error(msg);
    } finally {
      setConnecting(false);
    }
  };

  const handleSwitchAccount = async () => {
    setShowWalletMenu(false);
    if (typeof window === "undefined" || !window.ethereum) return;
    setConnecting(true);
    try {
      const accounts = await window.ethereum.request({ method: "eth_requestAccounts" });
      const address = accounts?.[0];
      if (!address) {
        setConnecting(false);
        return;
      }
      await authApi.updateWallet(address);
      setWalletAddress(address);
      toast.success(`Switched to ${address.slice(0, 6)}...${address.slice(-4)}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to switch account";
      toast.error(msg);
    } finally {
      setConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    setShowWalletMenu(false);
    try {
      await authApi.updateWallet(null);
      setWalletAddress(null);
      toast.success("Wallet disconnected");
    } catch {
      toast.error("Failed to disconnect");
    }
  };

  const handleLogout = () => {
    setShowUserMenu(false);
    setAccessToken(null);
    setUsername(null);
    setWalletAddress(null);
    window.location.href = "/dashboard";
  };

  return (
    <div className="topbar">
      <div>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
      <div className="topbar-pills">
        <span className="pill">
          <span className="dot" />
          Revive Testnet
        </span>
        <span className="pill">RPC Connected</span>
        <span className="pill">Storage SQLite/JSON</span>
        {username && (
          <div ref={userMenuRef} style={{ position: "relative" }}>
            <button
              type="button"
              className="wallet-btn"
              onClick={() => setShowUserMenu((v) => !v)}
              style={{ fontFamily: "inherit" }}
            >
              {username}
            </button>
            {showUserMenu && (
              <div
                className="wallet-menu"
                style={{
                  position: "absolute",
                  top: "100%",
                  right: 0,
                  marginTop: 6,
                  minWidth: 140,
                  padding: "8px 0",
                  background: "var(--bg-2)",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                  boxShadow: "0 4px 12px rgba(0,0,0,0.2)",
                  zIndex: 100,
                }}
              >
                <div style={{ padding: "8px 12px", fontSize: 11, color: "var(--text-3)" }}>
                  Logged in as <strong>{username}</strong>
                </div>
                <button
                  type="button"
                  className="wallet-menu-item"
                  onClick={handleLogout}
                  style={{
                    display: "block",
                    width: "100%",
                    padding: "8px 12px",
                    border: "none",
                    background: "none",
                    color: "var(--text-2)",
                    fontSize: 13,
                    textAlign: "left",
                    cursor: "pointer",
                  }}
                >
                  Log out
                </button>
              </div>
            )}
          </div>
        )}
        <div ref={menuRef} style={{ position: "relative" }}>
          <button
            type="button"
            className="wallet-btn"
            onClick={handleConnectWallet}
            disabled={connecting}
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <rect x="1" y="3" width="12" height="9" rx="2" stroke="currentColor" strokeWidth="1.4"/>
              <path d="M9.5 7.5a1 1 0 100-2 1 1 0 000 2z" fill="currentColor"/>
            </svg>
            {connecting
              ? "Connecting..."
              : walletAddress
                ? `${walletAddress.slice(0, 6)}...${walletAddress.slice(-4)}`
                : "Connect MetaMask"}
          </button>
          {showWalletMenu && walletAddress && (
            <div
              className="wallet-menu"
              style={{
                position: "absolute",
                top: "100%",
                right: 0,
                marginTop: 6,
                minWidth: 160,
                padding: "8px 0",
                background: "var(--bg-2)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                boxShadow: "0 4px 12px rgba(0,0,0,0.2)",
                zIndex: 100,
              }}
            >
              <div style={{ padding: "8px 12px", fontSize: 11, color: "var(--text-3)", wordBreak: "break-all" }}>
                {walletAddress}
              </div>
              <button
                type="button"
                className="wallet-menu-item"
                onClick={handleSwitchAccount}
                disabled={connecting}
                style={{
                  display: "block",
                  width: "100%",
                  padding: "8px 12px",
                  border: "none",
                  background: "none",
                  color: "var(--text-1)",
                  fontSize: 13,
                  textAlign: "left",
                  cursor: "pointer",
                }}
              >
                Switch account
              </button>
              <button
                type="button"
                className="wallet-menu-item"
                onClick={handleDisconnect}
                style={{
                  display: "block",
                  width: "100%",
                  padding: "8px 12px",
                  border: "none",
                  background: "none",
                  color: "var(--text-2)",
                  fontSize: 13,
                  textAlign: "left",
                  cursor: "pointer",
                }}
              >
                Disconnect
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
