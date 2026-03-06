import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Check } from "lucide-react"
import { PRODUCTS } from "@/lib/products"
import { cn } from "@/lib/utils"

export function Pricing() {
  return (
    <section id="pricing" className="py-20 sm:py-32 bg-card">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
            Simple, transparent pricing
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            Choose the plan that scales with your AI ambitions. All plans include a 14-day free trial.
          </p>
        </div>

        <div className="mt-16 grid gap-8 lg:grid-cols-3">
          {PRODUCTS.map((product) => (
            <div
              key={product.id}
              className={cn(
                "relative flex flex-col rounded-2xl border bg-background p-8",
                product.popular
                  ? "border-foreground ring-1 ring-foreground"
                  : "border-border"
              )}
            >
              {product.popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <span className="rounded-full bg-foreground px-4 py-1 text-xs font-semibold text-background">
                    Most Popular
                  </span>
                </div>
              )}

              <div className="mb-6">
                <h3 className="text-lg font-semibold text-foreground">
                  {product.name}
                </h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  {product.description}
                </p>
              </div>

              <div className="mb-6">
                <span className="text-4xl font-bold text-foreground">
                  ${(product.priceInCents / 100).toFixed(0)}
                </span>
                <span className="text-muted-foreground">/month</span>
              </div>

              <ul className="mb-8 flex-1 space-y-3">
                {product.features.map((feature) => (
                  <li key={feature} className="flex items-start gap-3">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-foreground" />
                    <span className="text-sm text-muted-foreground">
                      {feature}
                    </span>
                  </li>
                ))}
              </ul>

              <Button
                variant={product.popular ? "default" : "outline"}
                className="w-full"
                asChild
              >
                <Link href={`/checkout/${product.id}`}>
                  Get started
                </Link>
              </Button>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
