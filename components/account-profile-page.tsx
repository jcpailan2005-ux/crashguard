'use client'
import { useAuth } from '@/components/auth-provider'
import { PageHeading } from '@/components/page-heading'
import { Card } from '@/components/ui/card'
export function AccountProfilePage() { const { profile } = useAuth(); return <><PageHeading title="Account profile" description="Identity and scope loaded from the authenticated PostgreSQL session." /><Card className="space-y-2 p-5"><p className="text-lg font-semibold">{profile?.displayName}</p><p className="text-sm text-muted-foreground">{profile?.email}</p><p className="text-sm">Role: {profile?.role.toUpperCase()}</p><p className="text-sm">Area: {profile?.areaId ?? 'Unassigned'}</p></Card></> }
