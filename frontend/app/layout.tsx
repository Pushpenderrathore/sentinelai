import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  title: "SentinelAI: Autonomous Threat Detection",
  description: "AI-powered security auditing and exam integrity platform",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-sentinel-bg text-slate-200 antialiased">
        {children}
      </body>
    </html>
  )
}
