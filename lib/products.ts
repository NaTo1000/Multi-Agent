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
      "Up to 3 orchestration agents",
      "10,000 API calls/month",
      "Basic fleet orchestration",
      "OTA firmware generation",
      "WiFi and BLE device support",
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
      "Up to 15 orchestration agents",
      "100,000 API calls/month",
      "Advanced fleet orchestration",
      "GPS/GNSS telemetry support",
      "Priority support",
      "Low latency",
      "Custom workflows",
      "Analytics dashboard",
      "Webhook and scheduler automation",
    ],
    popular: true,
  },
  {
    id: "enterprise",
    name: "Enterprise",
    description: "For large organizations with custom needs",
    priceInCents: 29900, // $299/month
    features: [
      "Unlimited orchestration agents",
      "Unlimited API calls",
      "Enterprise fleet orchestration",
      "Dedicated support",
      "Ultra-low latency",
      "Custom integrations",
      "SLA guarantee",
      "On-premise option",
      "Multi-cloud connector support",
      "Custom firmware pipelines",
    ],
  },
]
