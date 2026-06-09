# Malayalam Music Randomizer

A high-performance, single-page random music player that streams official Malayalam music videos from YouTube, categorized by genre. 

The application utilizes a **decoupled architecture**:
1. **Frontend**: A static Vite + Vanilla JS/CSS client hosted for free on GitHub Pages. It reads a static `songs.json` database.
2. **Backend**: A Python sync worker running on GitHub Actions daily. It queries Last.fm for trending tracks per genre, maps them to YouTube video IDs, and commits the updated data to the repo, triggering an auto-deploy.

---

## Features

- **Premium Interface**: Dark mode with ambient glowing radial gradients and a glassmorphic aesthetic.
- **Micro-animations**: Active CSS-only equalizer visualizer and fluid button hover states.
- **Smart Randomizer**: Selects random songs within a chosen genre, keeping track of history to prevent immediate repeats.
- **Zero Hosting Costs**: Served entirely from static hosts (GitHub Pages/Vercel) with no 24/7 backend database.
- **Quota Safety**: Scrapes YouTube only once a day on the backend instead of on every user click, keeping searches within YouTube's daily free quota limits.

---

## Local Development Setup

### 1. Prerequisites
- [Node.js](https://nodejs.org/) (v16+)
- [Python 3](https://www.python.org/) (for the backend aggregator)

### 2. Frontend Development
Install node packages and launch the Vite dev server:
```bash
# Install dependencies
npm install

# Run Vite local server
npm run dev
```
Open `http://localhost:5173/` in your browser. The app will load mock tracks from `public/songs.json` immediately.

### 3. Running the Sync Script Locally
To fetch new tracks from the API manually, you will need your API keys set in your environment:
```bash
# Navigate to backend and install requirements
pip install -r backend/requirements.txt

# Run the python sync script (Windows PowerShell)
$env:LASTFM_API_KEY="your_lastfm_key"
$env:YOUTUBE_API_KEY="your_youtube_key"
python backend/sync_songs.py
```

---

## Setting up API Keys & Github Actions

To run the daily aggregator in GitHub Actions automatically, you need to set up free API Keys.

### Step 1: Get a free Last.fm API Key
1. Go to [Last.fm API Accounts Page](https://www.last.fm/api/account/create).
2. Register a new API Account (No payment or credit card required).
3. Copy the **API Key** generated.

### Step 2: Get a free YouTube Data API Key
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project or select an existing one.
3. Enable the **YouTube Data API v3** in the API Library.
4. Go to **Credentials**, click **Create Credentials**, and select **API Key**. Copy your API Key.

### Step 3: Add Secrets to GitHub Repository
Once you push this project to a GitHub repository:
1. Go to your repository on GitHub.
2. Click **Settings** -> **Secrets and variables** -> **Actions**.
3. Add two repository secrets:
   - `LASTFM_API_KEY` (Paste your Last.fm API Key)
   - `YOUTUBE_API_KEY` (Paste your Google/YouTube API Key)

The GitHub Action (`.github/workflows/sync.yml`) will now run automatically at **midnight UTC** every day, scrape fresh tracks, and push updates back to your repository.
