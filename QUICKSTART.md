# Quick Start Guide

Get up and running with the Car Crash Detection System in 5 minutes.

## Installation

```bash
# Clone or download the project
cd car-crash-detection

# Install dependencies
npm install
# or
pnpm install
```

## Configuration

Create `.env.local`:

```bash
# For development with mock data (no backend needed)
echo "NEXT_PUBLIC_USE_MOCK_DATA=true" > .env.local

# For production with backend
echo "NEXT_PUBLIC_BACKEND_URL=http://localhost:8000" > .env.local
echo "NEXT_PUBLIC_USE_MOCK_DATA=false" >> .env.local
```

## Run Development Server

```bash
npm run dev
```

Then open http://localhost:3000 in your browser.

## First Steps

1. **Explore the landing page** - Click "Go to Dashboard"
2. **View dashboard** - See mock statistics and recent incidents
3. **Try upload** - Drag a test image/video or click "Select File"
4. **Check the map** - View incidents on an interactive map
5. **View notifications** - See alert history

## Using Mock Data

The app includes mock data for demo purposes. To use it:

1. Keep `NEXT_PUBLIC_USE_MOCK_DATA=true` in `.env.local`
2. Dashboard will show sample incidents
3. Upload page shows demo results (30% chance to use mock detection)
4. All features work without a backend

## Connect Your FastAPI Backend

1. **Start your backend:**
   ```bash
   python main.py  # or uvicorn main:app --reload
   ```

2. **Update environment:**
   ```bash
   echo "NEXT_PUBLIC_BACKEND_URL=http://localhost:8000" > .env.local
   echo "NEXT_PUBLIC_USE_MOCK_DATA=false" >> .env.local
   ```

3. **Restart dev server:**
   ```bash
   npm run dev
   ```

4. **Test detection:**
   - Upload an image/video
   - Backend processes it with YOLO
   - Results display in real-time

## File Locations

| File | Purpose |
|------|---------|
| `app/page.tsx` | Landing page |
| `app/dashboard/page.tsx` | Main dashboard |
| `app/dashboard/upload/page.tsx` | Upload & detection |
| `app/dashboard/map/page.tsx` | Live map |
| `app/dashboard/notifications/page.tsx` | Alerts |
| `lib/api-client.ts` | Backend communication |
| `lib/types.ts` | Data types |

## Useful Commands

```bash
# Development
npm run dev          # Start dev server

# Production
npm run build        # Build app
npm start            # Start production server

# Code quality
npm run lint         # Check code style

# Build optimization
npm run build -- --debug  # Build with debug info
```

## API Endpoints Expected

If using a real backend, ensure these exist:

- `POST /api/detect/image` - Detect in images
- `POST /api/detect/video` - Detect in videos
- `GET /api/incidents` - Get all incidents
- `GET /api/notifications` - Get alerts
- `GET /api/health` - Backend status

## Troubleshooting

### "Cannot find module" error

```bash
# Clear and reinstall
rm -rf node_modules
npm install
npm run dev
```

### Map doesn't load

- Leaflet requires dynamic import
- Make sure JavaScript is enabled
- Check browser console for errors

### Backend connection fails

```bash
# Check backend is running
curl http://localhost:8000/api/health

# Verify URL in .env.local
cat .env.local

# Check CORS is enabled in backend
```

### Alert sound doesn't play

1. Upload an `alert-sound.mp3` to `public/` folder
2. Or disable in Settings page
3. Browser may require user interaction first

## Next Steps

1. **Read Full Docs:** See `README.md`
2. **Setup Backend:** Follow `BACKEND_INTEGRATION.md`
3. **Deploy:** Check `DEPLOYMENT.md`
4. **Customize:** Modify colors in `app/globals.css`

## Common Tasks

### Change Theme Colors

Edit `app/globals.css`:

```css
:root {
  --primary: oklch(0.65 0.22 41.116);  /* Orange */
  --destructive: oklch(0.577 0.245 27.325);  /* Red */
  /* ... other colors ... */
}
```

### Add New Page

Create `app/dashboard/newpage/page.tsx`:

```tsx
'use client'

import { Sidebar, DashboardHeader } from '@/components/dashboard-sidebar'

export default function NewPage() {
  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <div className="flex-1">
        <DashboardHeader />
        <main className="p-6">
          Your content here
        </main>
      </div>
    </div>
  )
}
```

### Use an API Service

```tsx
import { getIncidents, getNotifications } from '@/lib/api-client'

// In a component or page
const incidents = await getIncidents()
const notifications = await getNotifications()
```

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_BACKEND_URL` | `http://localhost:8000` | FastAPI backend URL |
| `NEXT_PUBLIC_USE_MOCK_DATA` | `true` | Use demo data when backend unavailable |
| `NODE_ENV` | `development` | Development or production mode |

## Browser Support

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Mobile browsers

## Performance Tips

1. **Build for production:** `npm run build`
2. **Use CDN for assets:** Configure in Vercel/hosting
3. **Enable compression:** Automatic with Next.js
4. **Optimize images:** Already done via shadcn/ui

## Security

Before deploying to production:

- [ ] Set secure backend URL
- [ ] Enable HTTPS/SSL
- [ ] Remove `NEXT_PUBLIC_USE_MOCK_DATA`
- [ ] Configure CORS properly
- [ ] Add authentication if needed
- [ ] Use environment variables for secrets

## Deployment Quick Links

- **Vercel:** https://vercel.com/new (recommended)
- **Docker:** Build with provided Dockerfile
- **Manual:** SSH to server, clone, npm install, npm run build

## Support Resources

- **Full Documentation:** README.md
- **Backend Setup:** BACKEND_INTEGRATION.md
- **Deployment:** DEPLOYMENT.md
- **Project Details:** PROJECT_SUMMARY.md

## Tips for School/Demo

1. **Keep mock data enabled** for instant results
2. **Use sample CCTV gallery** to showcase features
3. **Show the map** to demonstrate location tracking
4. **Trigger alert sound** to show real-time notifications
5. **Explain backend integration** to teachers/judges
6. **Show code structure** to demonstrate organization

---

**Enjoy building! For detailed info, see the full documentation files.**
