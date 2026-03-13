import Link from "next/link"
import { Bot } from "lucide-react"

export function Footer() {
  return (
    <footer className="border-t border-border bg-background py-12">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col items-center justify-between gap-6 sm:flex-row">
          <div className="flex items-center gap-2">
            <Bot className="h-5 w-5 text-muted-foreground" />
            <span className="text-sm font-medium text-muted-foreground">Multi-Agent</span>
          </div>
          
          <nav className="flex flex-wrap items-center justify-center gap-6">
            <Link href="#" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
              Privacy
            </Link>
            <Link href="#" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
              Terms
            </Link>
            <Link href="#" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
              Contact
            </Link>
          </nav>

          <p className="text-sm text-muted-foreground">
            &copy; 2026 Multi-Agent. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
  )
}
