'use client'

import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Camera, BarChart3, MapPin } from 'lucide-react'

export default function Home() {
  return (
    <main className="min-h-screen bg-background text-foreground flex flex-col">
      {/* Hero Section */}
      <section className="flex-1 flex items-center justify-center px-4 py-20">
        <div className="max-w-2xl text-center space-y-8">
          {/* Camera Icon with border */}
          <div className="flex justify-center">
            <div className="w-20 h-20 rounded-lg border border-primary bg-primary/10 flex items-center justify-center">
              <Camera className="w-10 h-10 text-primary" />
            </div>
          </div>

          {/* Title */}
          <h1 className="text-5xl md:text-6xl font-bold text-balance">
            Car Crash Detection System
          </h1>

          {/* Subtitle */}
          <p className="text-xl text-muted-foreground text-balance">
            Upload CCTV images and videos to detect possible traffic accidents
            using advanced AI-powered computer vision
          </p>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row gap-4 justify-center pt-4">
            <Link href="/login">
              <Button size="lg" className="w-full sm:w-auto">
                Sign in
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="bg-card/50 border-t border-border py-16 px-4">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold mb-12 text-center">Features</h2>
          <div className="grid md:grid-cols-3 gap-6">
            <Card className="p-6 border border-border bg-card/70 hover:bg-card/90 transition-colors">
              <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center mb-4">
                <Camera className="w-6 h-6 text-primary" />
              </div>
              <h3 className="font-semibold text-lg mb-2">Smart Detection</h3>
              <p className="text-muted-foreground">
                Advanced YOLO models detect accidents with high accuracy
              </p>
            </Card>

            <Card className="p-6 border border-border bg-card/70 hover:bg-card/90 transition-colors">
              <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center mb-4">
                <BarChart3 className="w-6 h-6 text-primary" />
              </div>
              <h3 className="font-semibold text-lg mb-2">Live Analytics</h3>
              <p className="text-muted-foreground">
                Track incidents and monitor detection history in real-time
              </p>
            </Card>

            <Card className="p-6 border border-border bg-card/70 hover:bg-card/90 transition-colors">
              <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center mb-4">
                <MapPin className="w-6 h-6 text-primary" />
              </div>
              <h3 className="font-semibold text-lg mb-2">Location Mapping</h3>
              <p className="text-muted-foreground">
                Visualize detected accidents on an interactive map
              </p>
            </Card>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border py-6 px-4 text-center text-sm text-muted-foreground">
        <p>Car Crash Detection System • Built with YOLO v11</p>
      </footer>
    </main>
  )
}
