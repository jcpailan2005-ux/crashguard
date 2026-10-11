import Link from 'next/link'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

export default function RegistrationClosedPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4">
      <Card className="w-full max-w-md space-y-4 p-6 text-center">
        <h1 className="text-2xl font-bold">Registration is administrator-managed</h1>
        <p className="text-sm text-muted-foreground">
          Public sign-up is disabled. Ask a CrashGuard administrator to create your account and issue a one-time password.
        </p>
        <Button asChild className="w-full"><Link href="/login">Back to sign in</Link></Button>
      </Card>
    </main>
  )
}
