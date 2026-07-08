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
            Run ESP32 fleets with AI agents that stay in sync.
          </h1>
          <p className="mt-6 text-lg leading-relaxed text-muted-foreground sm:text-xl">
            Multi-Agent combines orchestration, live telemetry, OTA firmware generation,
            GPS/GNSS awareness, and cloud automation so you can operate connected devices
            from a single control plane.
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

        <div className="mt-20">
          <p className="text-center text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Built for production device operations
          </p>
          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { value: "OTA Firmware", label: "Build, assemble, and deploy firmware updates" },
              { value: "WiFi + BLE", label: "Coordinate devices across multiple transport layers" },
              { value: "GPS / GNSS", label: "Track field telemetry with live position context" },
              { value: "Cloud Ready", label: "Route events to HTTP, AWS, GCP, and Azure" },
            ].map((item) => (
              <div
                key={item.value}
                className="rounded-2xl border border-border bg-card/60 p-5 text-left"
              >
                <div className="text-lg font-semibold text-foreground">{item.value}</div>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  {item.label}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
