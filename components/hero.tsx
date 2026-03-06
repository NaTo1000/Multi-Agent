import Link from "next/link"
import { Button } from "@/components/ui/button"
import { ArrowRight } from "lucide-react"

export function Hero() {
  return (
    <section className="relative overflow-hidden pt-32 pb-20 sm:pt-40 sm:pb-32">
      {/* Gradient background */}
      <div className="absolute inset-0 -z-10">
        <div className="absolute left-1/2 top-0 -translate-x-1/2 h-[500px] w-[800px] rounded-full bg-blue-600/20 blur-[120px]" />
      </div>

      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center">
          <h1 className="text-4xl font-bold tracking-tight text-foreground sm:text-6xl lg:text-7xl text-balance">
            Ship AI products that work.
          </h1>
          <p className="mt-6 text-lg leading-relaxed text-muted-foreground sm:text-xl">
            The end-to-end platform for building world-class multi-agent AI systems. 
            Orchestrate, deploy, and scale AI agents with confidence.
          </p>
          <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Button size="lg" asChild>
              <Link href="#pricing">
                Get started
              </Link>
            </Button>
            <Button variant="outline" size="lg" asChild>
              <Link href="#features">
                Learn more <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
          </div>
        </div>

        {/* Trusted by logos */}
        <div className="mt-20">
          <p className="text-center text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Trusted by AI teams at
          </p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-x-12 gap-y-6">
            {["Stripe", "Vercel", "Notion", "Zapier", "Airtable"].map((company) => (
              <span key={company} className="text-lg font-semibold text-muted-foreground/60">
                {company}
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
