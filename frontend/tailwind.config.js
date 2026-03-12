/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        panel: "var(--panel)",
        panel2: "var(--panel-2)",
        line: "var(--line)",
        text: "var(--text)",
        text2: "var(--text-2)",
        text3: "var(--text-3)",
        brand: "var(--brand)",
        brand2: "var(--brand-2)",
        green: "var(--green)",
        amber: "var(--amber)",
        red: "var(--red)",
        cyan: "var(--cyan)",
      },
      fontFamily: {
        inter: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
