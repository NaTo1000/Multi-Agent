import Link from "next/link"
import { Button } from "@/components/ui/button"
import { CheckCircle2 } from "lucide-react"

export default function SuccessPage() {
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

        <p className="mt-2 text-sm text-muted-foreground">
          A confirmation email has been sent to your email address.
        </p>

        <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:justify-center">
          <Button asChild>
            <Link href="/dashboard">
              Go to Dashboard
            </Link>
          </Button>
          <Button variant="outline" asChild>
            <Link href="/">
              Back to Home
            </Link>
          </Button>
        </div>
      </div>
    </div>
  )
}
