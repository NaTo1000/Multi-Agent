export interface Product {
  id: string
  name: string
  description: string
  priceInCents: number
  features: string[]
  popular?: boolean
}

export const PRODUCTS: Product[] = [
  {
    id: "starter",
    name: "Starter",
    description: "Perfect for individuals and small projects",
    priceInCents: 2900, // $29/month
    features: [
      "Up to 3 AI agents",
      "10,000 API calls/month",
      "Basic orchestration",
      "Community support",
      "Standard latency",
    ],
  },
  {
    id: "pro",
    name: "Pro",
    description: "For growing teams and production workloads",
    priceInCents: 9900, // $99/month
    features: [
      "Up to 15 AI agents",
      "100,000 API calls/month",
      "Advanced orchestration",
      "Priority support",
      "Low latency",
      "Custom workflows",
      "Analytics dashboard",
    ],
    popular: true,
  },
  {
    id: "enterprise",
    name: "Enterprise",
    description: "For large organizations with custom needs",
    priceInCents: 29900, // $299/month
    features: [
      "Unlimited AI agents",
      "Unlimited API calls",
      "Enterprise orchestration",
      "Dedicated support",
      "Ultra-low latency",
      "Custom integrations",
      "SLA guarantee",
      "On-premise option",
    ],
  },
]
