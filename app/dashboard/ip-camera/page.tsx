'use client'

import { CctvMonitorWorkspace } from '@/components/cctv-monitor-workspace'
import { Sidebar } from '@/components/dashboard-sidebar'

export default function IpCameraPage() {
  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <div className="min-w-0 flex-1 md:ml-0">
        <CctvMonitorWorkspace />
      </div>
    </div>
  )
}
