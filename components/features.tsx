import { 
  Zap, 
  GitBranch, 
  Shield, 
  BarChart3, 
  Workflow, 
  Globe 
} from "lucide-react"

const features = [
  {
    icon: Zap,
    title: "Fleet orchestration",
    description: "Coordinate ESP32 modules and specialized agents from one runtime without losing observability.",
    bullets: [
      "Concurrent task scheduling across device fleets",
      "Agent routing for frequency, modulation, comms, firmware, and AI",
      "REST and WebSocket control surfaces for operators and dashboards",
    ],
  },
  {
    icon: GitBranch,
    title: "Adaptive radio control",
    description: "Respond to real-world interference with intelligent scanning, locking, and tuning workflows.",
    bullets: [
      "Band scan, lock, and fine-tune device frequencies",
      "Adaptive modulation strategies for changing link conditions",
      "Fleet-wide synchronization for coordinated rollouts",
    ],
  },
  {
    icon: Shield,
    title: "Resilient operations",
    description: "Keep device operations dependable with telemetry retention, health checks, and protected admin tooling.",
    bullets: [
      "Structured event logging with audit and error views",
      "Health monitors, scheduler jobs, and webhook automation",
      "Admin configuration, terminal, and recovery workflows",
    ],
  },
  {
    icon: BarChart3,
    title: "Live telemetry",
    description: "Track device state, events, and orchestration activity as it happens across your deployment.",
    bullets: [
      "Real-time event streaming over WebSocket",
      "Centralized metrics for agents, tasks, and mirror snapshots",
      "Audit trails that help operators diagnose incidents quickly",
    ],
  },
  {
    icon: Workflow,
    title: "Firmware automation",
    description: "Assemble feature-based firmware variants and deliver them to devices without leaving the platform.",
    bullets: [
      "On-the-fly firmware generation from reusable templates",
      "Optional compile-and-flash flows for OTA updates",
      "Feature modules for WiFi, BLE, GPS, and custom defines",
    ],
  },
  {
    icon: Globe,
    title: "Connected everywhere",
    description: "Bridge local device control with cloud systems and mobile clients built for field operations.",
    bullets: [
      "HTTP, AWS IoT, GCP Pub/Sub, and Azure IoT integrations",
      "Cross-platform mobile companion for iOS and Android",
      "GPS/GNSS and BLE support for hardware-aware workflows",
    ],
  },
]

export function Features() {
  return (
    <section id="features" className="py-20 sm:py-32">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl text-balance">
            Everything you need to build AI products
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            A complete platform for orchestrating, deploying, and scaling multi-agent AI systems.
          </p>
        </div>

        <div className="mt-16 grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((feature) => (
            <div
              key={feature.title}
              className="group rounded-xl border border-border bg-card p-6 transition-colors hover:border-muted-foreground/30"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-secondary">
                <feature.icon className="h-5 w-5 text-foreground" />
              </div>
              <h3 className="mt-4 text-lg font-semibold text-foreground">
                {feature.title}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                {feature.description}
              </p>
              <ul className="mt-4 space-y-2">
                {feature.bullets.map((bullet) => (
                  <li key={bullet} className="text-sm leading-relaxed text-muted-foreground">
                    • {bullet}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
