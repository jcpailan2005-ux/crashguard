# Deployment Guide

This guide covers deploying the Car Crash Detection System frontend to production.

## Prerequisites

- Node.js 18+ installed
- Git repository (for continuous deployment)
- FastAPI backend deployed and accessible

## Local Testing

Before deploying, test locally:

```bash
# Install dependencies
npm install

# Build the app
npm run build

# Start production server
npm start
```

Visit http://localhost:3000 and verify all features work.

## Environment Setup

Create `.env.local` with these variables:

```bash
# Backend API URL (must be publicly accessible if deployed)
NEXT_PUBLIC_BACKEND_URL=https://your-api.example.com

# Use mock data for demo (set to false in production)
NEXT_PUBLIC_USE_MOCK_DATA=false
```

## Deployment Options

### Option 1: Vercel (Recommended)

Vercel offers zero-config deployment for Next.js applications with automatic CI/CD.

**Steps:**

1. **Push to GitHub**
   ```bash
   git add .
   git commit -m "Initial commit"
   git push origin main
   ```

2. **Connect to Vercel**
   - Go to https://vercel.com/new
   - Import your GitHub repository
   - Select "Next.js" preset (auto-detected)
   - Click "Deploy"

3. **Set Environment Variables**
   - Project Settings → Environment Variables
   - Add `NEXT_PUBLIC_BACKEND_URL`
   - Add `NEXT_PUBLIC_USE_MOCK_DATA=false`

4. **Configure Domain**
   - Project Settings → Domains
   - Add custom domain or use Vercel subdomain
   - DNS configuration instructions provided

**Automatic Deployments:**
- Merges to `main` automatically deploy to production
- Pull requests get preview URLs

### Option 2: Docker

Deploy using Docker containers.

**Dockerfile:**

```dockerfile
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM node:18-alpine
WORKDIR /app

ENV NODE_ENV=production

COPY package*.json ./
RUN npm ci --only=production

COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public

EXPOSE 3000
CMD ["npm", "start"]
```

**Build and run:**

```bash
# Build image
docker build -t crash-detection-frontend:latest .

# Run container
docker run -p 3000:3000 \
  -e NEXT_PUBLIC_BACKEND_URL=https://your-api.example.com \
  -e NEXT_PUBLIC_USE_MOCK_DATA=false \
  crash-detection-frontend:latest
```

**Push to registry:**

```bash
# Docker Hub
docker tag crash-detection-frontend:latest yourname/crash-detection-frontend:latest
docker push yourname/crash-detection-frontend:latest

# Or private registry
docker tag crash-detection-frontend:latest registry.example.com/crash-detection:latest
docker push registry.example.com/crash-detection:latest
```

### Option 3: Traditional VPS (Ubuntu/Debian)

Deploy to a virtual private server.

**Setup:**

```bash
# SSH into server
ssh user@your-server.com

# Install Node.js
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Clone repository
git clone https://github.com/yourusername/crash-detection.git
cd crash-detection

# Install dependencies
npm install

# Build
npm run build

# Create .env.local
echo "NEXT_PUBLIC_BACKEND_URL=https://your-api.example.com" > .env.local
echo "NEXT_PUBLIC_USE_MOCK_DATA=false" >> .env.local

# Start with PM2 (process manager)
sudo npm install -g pm2
pm2 start "npm start" --name crash-detection
pm2 startup
pm2 save
```

**Setup Nginx Reverse Proxy:**

```nginx
server {
    listen 80;
    server_name crash-detection.example.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

Enable SSL with Let's Encrypt:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d crash-detection.example.com
```

### Option 4: AWS

Deploy to AWS using various services.

**Using Amplify:**

1. Connect GitHub repo to AWS Amplify
2. Configure build settings
3. Add environment variables
4. Deploy with automatic rollbacks

**Using ECS + Fargate:**

1. Push Docker image to ECR
2. Create ECS task definition
3. Deploy to Fargate cluster
4. Setup load balancer

**Using EC2:**

Similar to VPS approach - provision instance, install Node.js, deploy application.

## Performance Optimization

### 1. Enable Compression

Already enabled by Next.js, verify in headers:

```bash
curl -I https://your-app.com | grep -i content-encoding
```

### 2. Image Optimization

Next.js automatically optimizes images. The app uses optimized images via shadcn/ui components.

### 3. Caching Strategy

```
Static assets: Cache forever with versioning
HTML pages: Cache for 1 hour
API responses: Cache per request as configured
```

### 4. Database Connection Pooling

If using external API, implement connection pooling in backend.

## Monitoring

### Application Monitoring

**Vercel Analytics** (included with Vercel deployment):
- Real-time metrics
- Performance monitoring
- Error tracking

**Sentry** (optional):

```javascript
import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: "YOUR_SENTRY_DSN",
  tracesSampleRate: 1.0,
});
```

### Backend Monitoring

Monitor FastAPI backend for:
- Response times
- Error rates
- Memory usage
- GPU utilization (if using GPU for YOLO)

### Uptime Monitoring

Use services like Uptime Robot or Pingdom to monitor availability:

- Ping frontend every 5 minutes
- Alert if down for more than 5 minutes
- Daily email reports

## Scaling

### Frontend Scaling

- CDN (CloudFront, Cloudflare) for static assets
- Multiple regions via Vercel/AWS
- Horizontal scaling with load balancer

### Backend Scaling

For YOLO inference workload:

- **GPU Instances**: For faster inference
- **Load Balancing**: Distribute requests across multiple backends
- **Caching**: Cache frequently analyzed content
- **Queue System**: Use Redis/Celery for async processing

## SSL/TLS Certificate

### Let's Encrypt (Free)

```bash
certbot certonly --standalone -d crash-detection.example.com
```

### AWS Certificate Manager (Free for AWS services)

In AWS Console:
1. Request public certificate
2. Validate ownership via DNS
3. Attach to load balancer/CloudFront

## Continuous Integration/Deployment

### GitHub Actions

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - uses: actions/setup-node@v3
        with:
          node-version: 18
      
      - run: npm ci
      - run: npm run build
      - run: npm run lint
      
      - name: Deploy to Vercel
        run: npx vercel --prod
        env:
          VERCEL_TOKEN: ${{ secrets.VERCEL_TOKEN }}
```

## Rollback Procedure

### Vercel
- Go to Deployments tab
- Click "Rollback" on previous working deployment

### Manual Rollback
```bash
git revert HEAD
git push origin main
npm run build && npm start
```

## Health Checks

Monitor endpoint availability:

```bash
# Check frontend
curl -I https://your-app.com

# Check backend connection
curl -s https://your-app.com/api/health | jq .

# Monitor with cron
0 */6 * * * curl -I https://your-app.com || send_alert
```

## Security Checklist

- [ ] Set environment variables securely (not in git)
- [ ] Enable HTTPS/SSL everywhere
- [ ] Configure CORS properly (specify allowed origins)
- [ ] Validate all user inputs
- [ ] Use security headers (CSP, X-Frame-Options, etc.)
- [ ] Keep dependencies updated
- [ ] Regular security audits (`npm audit`)
- [ ] Rate limiting on backend
- [ ] SQL injection protection (use parameterized queries)

## Troubleshooting

**App won't start:**
```bash
npm run build
npm start --debug
```

**Memory issues:**
```bash
# Increase Node.js memory
NODE_OPTIONS=--max-old-space-size=2048 npm start
```

**CORS errors:**
- Check backend CORS configuration
- Verify `NEXT_PUBLIC_BACKEND_URL` is correct
- Ensure backend is accessible from frontend

**API timeouts:**
- Increase backend timeout settings
- Optimize YOLO inference speed
- Implement caching for frequent requests

## Next Steps

1. Deploy frontend to production
2. Deploy FastAPI backend
3. Configure DNS/domains
4. Setup SSL certificates
5. Enable monitoring and alerting
6. Create backup strategy
7. Document operational procedures

---

For more info, see README.md and BACKEND_INTEGRATION.md
