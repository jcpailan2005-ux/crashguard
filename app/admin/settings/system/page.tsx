import { PageHeading } from '@/components/page-heading'
import { Card } from '@/components/ui/card'

export default function SystemSettingsPage() {
  return <><PageHeading title="System settings" description="Admin-only security and operational configuration." /><Card className="p-5 text-sm text-muted-foreground">Secrets and database credentials are intentionally managed outside this browser. Use the documented environment variables and restart the backend after changes. AI-specific controls remain under AI Configuration.</Card></>
}
