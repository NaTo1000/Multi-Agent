import Link from "next/link"
import { redirect } from "next/navigation"
import { Button } from "@/components/ui/button"
import { CheckCircle2, AlertCircle } from "lucide-react"
import { getCheckoutSessionStatus } from "@/app/actions/stripe"

interface SuccessPageProps {
  searchParams: Promise<{ session_id?: string }>
}

export default async function SuccessPage({ searchParams }: SuccessPageProps) {
  const { session_id } = await searchParams
  
  if (!session_id) {
    redirect("/")
  }

  const session = await getCheckoutSessionStatus(session_id)
  const isComplete = session.status === "complete"

  if (!isComplete) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-4">
        <div className="mx-auto max-w-md text-center">
          <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10">
            <AlertCircle className="h-8 w-8 text-destructive" />
          </div>
          
          <h1 className="text-2xl font-bold text-foreground">
            Payment Incomplete
          </h1>
          
          <p className="mt-4 text-muted-foreground">
            Your payment was not completed. Please try again or contact support if you continue to have issues.
          </p>

          <div className="mt-8">
            <Button asChild>
              <Link href="/#pricing">
                Try Again
              </Link>
            </Button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="mx-auto max-w-md text-center">
        <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-green-500/10">
          <CheckCircle2 className="h-8 w-8 text-green-500" />
        </div>
        
        <h1 className="text-2xl font-bold text-foreground">
          Payment Successful!
        </h1>
        
        <p className="mt-4 text-muted-foreground">
          Thank you for subscribing to Multi-Agent. You now have access to all the features included in your plan.
        </p>

        {session.customerEmail && (
          <p className="mt-2 text-sm text-muted-foreground">
            A confirmation email has been sent to <span className="font-medium text-foreground">{session.customerEmail}</span>.
          </p>
        )}

        <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:justify-center">
          <Button asChild>
            <Link href="/">
              Back to Home
            </Link>
          </Button>
        </div>
      </div>
    </div>
  )
}
