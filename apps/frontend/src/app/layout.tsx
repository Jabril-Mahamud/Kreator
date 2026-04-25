import type { ReactNode } from "react";

export const metadata = {
  title: "Kreator",
  description: "Kreator sample frontend",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body
        style={{
          fontFamily: "system-ui, sans-serif",
          margin: 0,
          padding: "2rem",
          background: "#0b0d10",
          color: "#e6e6e6",
        }}
      >
        {children}
      </body>
    </html>
  );
}
