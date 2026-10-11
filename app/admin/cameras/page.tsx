'use client'

import { useState } from 'react'
import { CctvMonitorWorkspace } from '@/components/cctv-monitor-workspace'
import { AdminCameraManagementTable } from '@/components/admin-camera-management-table'
import { PageHeading } from '@/components/page-heading'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

export default function AdminCamerasPage() {
  const [activeTab, setActiveTab] = useState('monitor')
  const [selectedCameraId, setSelectedCameraId] = useState<string | null>(null)
  const [refreshKey] = useState(0)

  return (
    <>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2">
        <PageHeading
          title="Cameras"
          description="Monitor live CCTV and camera infrastructure across active operational sectors."
        />
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList aria-label="Admin camera workspace">
          <TabsTrigger value="monitor">Live Monitor</TabsTrigger>
          <TabsTrigger value="management">Camera Management</TabsTrigger>
        </TabsList>
        <TabsContent value="monitor">
          <CctvMonitorWorkspace key={`monitor-${refreshKey}`} initialCameraId={selectedCameraId} />
        </TabsContent>
        <TabsContent value="management">
          <AdminCameraManagementTable
            key={`mgmt-${refreshKey}`}
            onViewCamera={(camera) => {
              setSelectedCameraId(camera.cameraId)
              setActiveTab('monitor')
            }}
          />
        </TabsContent>
      </Tabs>
    </>
  )
}
