# Lily - Contraction Tracker

A real-time contraction tracking app with family sync, time series visualizations, and statistical analysis.

## Features

- **One-tap logging** - Big start/stop button for easy tracking during labor
- **Real-time sync** - Family members see updates instantly via WebSocket
- **Time series charts** - Duration and interval trends over time
- **Statistical analysis** - Distribution charts, averages, and 5-1-1 rule indicator
- **Gap detection** - Handles breaks in labor with visual chart breaks
- **Dark mode** - Easier on the eyes during nighttime

## Quick Start

### Backend

```bash
cd backend
uv venv
uv pip install -r requirements.txt
uv run python main.py
```

Backend runs on http://localhost:8000

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on http://localhost:3000

## Tech Stack

- **Frontend**: React + Vite + Chart.js + Tailwind CSS
- **Backend**: Python (FastAPI) + SQLite
- **Real-time**: WebSockets

## 5-1-1 Rule

The app monitors for the 5-1-1 pattern that often indicates active labor:
- Contractions **5** minutes apart
- Lasting **1** minute each
- For **1** hour

When this pattern is detected, the app will highlight it so you know to contact your healthcare provider.

## API Endpoints

- `GET /contractions` - List all contractions
- `POST /contraction` - Start a new contraction
- `PUT /contraction/:id` - Update (end) a contraction
- `DELETE /contraction/:id` - Delete a contraction
- `WS /ws` - WebSocket for real-time updates

## Deployment

For single-server deployment, the FastAPI backend can serve the frontend as static files:

```bash
cd frontend && npm run build
# Copy dist/ to backend/static/ and serve via FastAPI
```

Or deploy separately:
- Backend: Railway, Fly.io, DigitalOcean
- Frontend: Vercel, Netlify, Cloudflare Pages
