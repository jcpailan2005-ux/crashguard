type CameraPrincipal = { role?: string; permissions?: string[] } | null
type CameraProtection = { cameraType?: string | null; streamUrl?: string | null; cameraIp?: string | null }

export function canManageCamera(principal: CameraPrincipal, action: 'create' | 'update' | 'disable'): boolean {
  if (!principal || !['admin', 'dispatcher'].includes(principal.role?.toLowerCase() ?? '')) return false
  return principal.permissions?.includes(`cameras.${action}`) === true
}

export function isProtectedCamera(camera: CameraProtection): boolean {
  return camera.cameraType?.toLowerCase() === 'demo' ||
    camera.streamUrl?.startsWith('demo://') === true || camera.cameraIp?.startsWith('demo-') === true
}
