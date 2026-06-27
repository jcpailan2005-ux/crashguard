'use client'

import { AlertTriangle } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'

interface PermissionMessageProps {
  onSignOut?: () => void
}

export function PermissionMessage({ onSignOut }: PermissionMessageProps) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-md space-y-4">
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>You do not have permission to access this page.</AlertDescription>
        </Alert>
        {onSignOut ? (
          <Button type="button" variant="outline" className="w-full" onClick={onSignOut}>
            Sign out
          </Button>
        ) : null}
      </div>
    </main>
  )
}
