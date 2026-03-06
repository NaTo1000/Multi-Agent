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
    title: "Lightning Fast",
    description: "Ultra-low latency orchestration ensures your AI agents respond in milliseconds, not seconds.",
  },
  {
    icon: GitBranch,
    title: "Advanced Orchestration",
    description: "Coordinate multiple AI agents with sophisticated routing, branching, and parallel execution.",
  },
  {
    icon: Shield,
    title: "Enterprise Security",
    description: "SOC 2 compliant infrastructure with end-to-end encryption and role-based access control.",
  },
  {
    icon: BarChart3,
    title: "Real-time Analytics",
    description: "Monitor agent performance, track costs, and optimize workflows with detailed insights.",
  },
  {
    icon: Workflow,
    title: "Custom Workflows",
    description: "Build complex multi-agent pipelines with our visual workflow builder or code-first SDK.",
  },
  {
    icon: Globe,
    title: "Global Edge Network",
    description: "Deploy agents closer to your users with automatic edge routing and failover.",
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
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
