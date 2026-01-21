# Railway Deployment Guide

## Quick Deploy (5 minutes)

### Step 1: Push to GitHub

```bash
cd trading-refinery
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/trading-refinery.git
git push -u origin main
```

### Step 2: Deploy Backend

1. Go to [railway.app](https://railway.app) and sign in with GitHub
2. Click **New Project** → **Deploy from GitHub repo**
3. Select your `trading-refinery` repo
4. When prompted, select the **backend** folder as root directory
5. Add environment variables in the **Variables** tab:
   ```
   QC_USER_ID=your_quantconnect_user_id
   QC_API_TOKEN=your_quantconnect_api_token
   ANTHROPIC_API_KEY=sk-ant-...
   ```
6. Railway will auto-deploy. Note the generated URL (e.g., `https://trading-refinery-backend-production.up.railway.app`)

### Step 3: Deploy Frontend

1. In the same Railway project, click **New** → **GitHub Repo**
2. Select the same repo again
3. This time select the **frontend** folder as root directory
4. Add environment variable:
   ```
   VITE_API_URL=https://your-backend-url-from-step-2.up.railway.app
   ```
5. Railway will build and deploy the frontend
6. Click **Settings** → **Generate Domain** to get your public URL

### Step 4: Access Your Dashboard

Open the frontend URL in any browser. You're done!

---

## Environment Variables Reference

### Backend
| Variable | Description |
|----------|-------------|
| `QC_USER_ID` | Your QuantConnect user ID (from account page) |
| `QC_API_TOKEN` | Your QuantConnect API token |
| `ANTHROPIC_API_KEY` | Your Anthropic API key |

### Frontend
| Variable | Description |
|----------|-------------|
| `VITE_API_URL` | Full URL of your deployed backend |

---

## Troubleshooting

**Build fails on backend**
- Check that `requirements.txt` is in the backend folder
- Verify Python version compatibility (3.11 recommended)

**Frontend can't connect to backend**
- Verify `VITE_API_URL` is set correctly (include https://)
- Check CORS settings if using custom domain

**WebSocket disconnects**
- Railway supports WebSockets by default
- If issues persist, check Railway logs for connection errors

**Loop stops unexpectedly**
- Check Railway logs: `railway logs`
- May be hitting QC API rate limits (add longer cooldown)
- Free tier has sleep after inactivity—upgrade to keep running 24/7

---

## Keeping It Running 24/7

Railway's free tier sleeps after inactivity. To keep the refinement loop running continuously:

1. **Upgrade to Hobby ($5/mo)**: No sleep, always running
2. **Or use a cron ping**: Set up UptimeRobot to ping your backend `/api/health` every 5 minutes

---

## Costs

- **Railway Hobby**: ~$5/month for always-on
- **QuantConnect**: Free tier has API limits; paid tier ($8/mo) for more backtests
- **Anthropic API**: ~$0.003 per analysis (Sonnet), so maybe $1-5/month depending on iteration frequency
