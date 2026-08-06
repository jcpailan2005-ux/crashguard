'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/components/auth-provider'

export default function LiveCameraRedirectPage() {
  const router = useRouter()
  const { profile, loading } = useAuth()

  useEffect(() => {
    if (loading) return
    if (profile?.role === 'admin') {
      router.replace('/dashboard/ip-camera')
    } else {
      router.replace('/dashboard')
    }
  }, [loading, profile, router])

  return null
}
