import { notFound } from "next/navigation"
import Link from "next/link"
import { ArrowLeft } from "lucide-react"
import { PRODUCTS } from "@/lib/products"
import { Checkout } from "@/components/checkout"

interface CheckoutPageProps {
  params: Promise<{ productId: string }>
}

export default async function CheckoutPage({ params }: CheckoutPageProps) {
  const { productId } = await params
  
  const product = PRODUCTS.find((p) => p.id === productId)
  
  if (!product) {
    notFound()
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6 lg:px-8">
        <Link
          href="/#pricing"
          className="mb-8 inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to pricing
        </Link>

        <div className="mb-8">
          <h1 className="text-2xl font-bold text-foreground">
            Subscribe to {product.name}
          </h1>
          <p className="mt-2 text-muted-foreground">
            {product.description} - ${(product.priceInCents / 100).toFixed(0)}/month
          </p>
        </div>

        <div className="rounded-xl border border-border bg-card p-6">
          <Checkout productId={productId} />
        </div>
      </div>
    </div>
  )
}

export function generateStaticParams() {
  return PRODUCTS.map((product) => ({
    productId: product.id,
  }))
}
