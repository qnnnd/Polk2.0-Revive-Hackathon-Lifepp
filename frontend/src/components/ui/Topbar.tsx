"use client";

interface TopbarProps {
  title: string;
  description: string;
}

export function Topbar({ title, description }: TopbarProps) {
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
        <button className="wallet-btn">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <rect x="1" y="3" width="12" height="9" rx="2" stroke="currentColor" strokeWidth="1.4"/>
            <path d="M9.5 7.5a1 1 0 100-2 1 1 0 000 2z" fill="currentColor"/>
          </svg>
          Connect MetaMask
        </button>
      </div>
    </div>
  );
}
