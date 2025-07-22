import type React from "react"
import type { Metadata } from "next"
import "./globals.css"
import { Toaster } from "sonner"

export const metadata: Metadata = {
  title: "Crux - Academic Research Agent",
  description: "Transform your research topics into comprehensive proofs and academic discoveries",
    generator: 'v0.dev'
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="font-mono antialiased">
        {children}
        <Toaster />
      </body>
    </html>
  )
}
