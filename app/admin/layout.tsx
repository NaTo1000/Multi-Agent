import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Admin | Multi-Agent",
  description: "Multi-Agent administration dashboard",
}

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
