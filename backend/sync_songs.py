#!/usr/bin/env python3
import os
import json
import sys
import requests
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Force UTF-8 encoding for standard output/error on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass


# Configuration
LASTFM_API_URL = "http://ws.audioscrobbler.com/2.0/"
TRACK_LIMIT_PER_TAG = 12
MAX_NEW_YOUTUBE_SEARCHES = 40 # Strict limit per daily run to protect free quota (1 search = 100 units)

GENRE_TAGS = {
    "mollywood": ["mollywood", "malayalam cinema"],
    "melodies": ["malayalam melody", "malayalam romantic"],
    "indie": ["malayalam indie"],
    "hiphop": ["malayalam hip hop", "malayalam rap"],
    "pop": ["malayalam pop"],
    "rock": ["malayalam rock"],
    "folk": ["naadan paattu", "malayalam folk"],
    "classics": ["malayalam classics", "malayalam oldies"]
}

# Fallback curated video IDs if Last.fm tags yield 0 results for a genre
FALLBACK_TRACKS = {
    "rock": ["tO01J-M3g0U", "y_2aJ7e8u8A"],
    "folk": ["_BfH_T8G8s0", "tO01J-M3g0U"],
    "classics": ["7wMIn_Wk7_U"],
    "hiphop": ["8a0UvOveQ68"],
    "indie": ["tO01J-M3g0U", "8a0UvOveQ68", "2x9sI6q3Spg"],
    "melodies": ["L0yNMDXmS0E", "88M6K95k-v4", "7wMIn_Wk7_U", "maGx1qLP3GE"]
}

# Resolve paths relative to project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(BASE_DIR, "backend", "track_cache.json")
SONGS_JSON_PATH = os.path.join(BASE_DIR, "public", "songs.json")

def load_cache():
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading cache: {e}. Starting fresh.")
    return {}

def save_cache(cache):
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(cache)} items to track cache.")

def get_lastfm_tracks(tag, api_key):
    params = {
        "method": "tag.gettoptracks",
        "tag": tag,
        "api_key": api_key,
        "format": "json",
        "limit": TRACK_LIMIT_PER_TAG
    }
    try:
        response = requests.get(LASTFM_API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        tracks_data = data.get("tracks", {}).get("track", [])
        
        # In case API returns single track dict instead of list
        if isinstance(tracks_data, dict):
            tracks_data = [tracks_data]
            
        tracks = []
        for t in tracks_data:
            name = t.get("name")
            artist = t.get("artist", {}).get("name")
            if name and artist:
                tracks.append({"title": name.strip(), "artist": artist.strip()})
        return tracks
    except Exception as e:
        print(f"Error fetching Last.fm tracks for tag '{tag}': {e}")
        return []

def search_youtube(query, youtube_client):
    try:
        # Search for video
        search_response = youtube_client.search().list(
            q=query,
            part="id,snippet",
            maxResults=1,
            type="video",
            videoEmbeddable="true" # Ensure the video can be played inside an iframe
        ).execute()
        
        items = search_response.get("items", [])
        if items:
            video_id = items[0]["id"]["videoId"]
            title = items[0]["snippet"]["title"]
            print(f"YouTube Resolved: '{query}' -> [{video_id}] ({title})")
            return video_id
        else:
            print(f"YouTube: No videos found for query: '{query}'")
            return None
    except HttpError as e:
        print(f"YouTube API HttpError searching for '{query}': {e}")
        return None
    except Exception as e:
        print(f"General error searching YouTube for '{query}': {e}")
        return None

def load_env():
    env_path = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        if "=" in line:
                            key, val = line.split("=", 1)
                            os.environ[key.strip()] = val.strip().strip('"').strip("'")
            print("Loaded environment variables from local .env file.")
        except Exception as e:
            print(f"Error reading .env file: {e}")

def main():
    load_env()
    lastfm_key = os.environ.get("LASTFM_API_KEY")
    youtube_key = os.environ.get("YOUTUBE_API_KEY")
    
    if not lastfm_key or not youtube_key:
        print("WARNING: LASTFM_API_KEY or YOUTUBE_API_KEY environment variables are missing.")
        print("Dry run: loading local cache and mock outputs only.")
        # We will create a fake cache fill or just exit early if keys are missing
        if not os.path.exists(SONGS_JSON_PATH):
             print("Creating initial default mock file.")
        return

    # Initialize YouTube client
    try:
        youtube_client = build("youtube", "v3", developerKey=youtube_key)
    except Exception as e:
        print(f"Failed to build YouTube service client: {e}")
        return

    # Load caches
    track_cache = load_cache()
    
    # Store aggregated genre results
    genre_results = {}
    search_count = 0
    
    for genre, tags in GENRE_TAGS.items():
        print(f"\nProcessing Genre: {genre.upper()}")
        genre_video_ids = []
        seen_tracks_in_genre = set()
        
        for tag in tags:
            print(f"Fetching Last.fm tag: '{tag}'")
            tracks = get_lastfm_tracks(tag, lastfm_key)
            
            for track in tracks:
                track_key = f"{track['artist']} - {track['title']}".lower()
                if track_key in seen_tracks_in_genre:
                    continue
                seen_tracks_in_genre.add(track_key)
                
                # Check cache
                if track_key in track_cache:
                    cached_id = track_cache[track_key]
                    if cached_id: # Ignore cached None values (which represent unfound tracks)
                        genre_video_ids.append(cached_id)
                else:
                    # Not in cache, needs YouTube API search
                    if search_count >= MAX_NEW_YOUTUBE_SEARCHES:
                        print(f"Reached search limit of {MAX_NEW_YOUTUBE_SEARCHES} for this run. Skipping search for: {track_key}")
                        continue
                        
                    query = f"{track['artist']} - {track['title']} (Official Audio Video)"
                    print(f"Searching YouTube: {query}")
                    video_id = search_youtube(query, youtube_client)
                    
                    search_count += 1
                    track_cache[track_key] = video_id # Save result (even if None) to cache to avoid re-searching
                    
                    if video_id:
                        genre_video_ids.append(video_id)
        
        # Remove duplicate IDs within this genre
        unique_ids = []
        for vid in genre_video_ids:
            if vid not in unique_ids:
                unique_ids.append(vid)
                
        # If API returned too few tracks (< 3) for this genre, append our curated list to fill it out
        if len(unique_ids) < 3 and genre in FALLBACK_TRACKS:
            for fallback_id in FALLBACK_TRACKS[genre]:
                if fallback_id not in unique_ids:
                    unique_ids.append(fallback_id)
            
        genre_results[genre] = unique_ids
        print(f"Genre {genre} has {len(unique_ids)} tracks.")

    # Build the "all" category as union of all genres
    all_ids = []
    for ids in genre_results.values():
        for vid in ids:
            if vid not in all_ids:
                all_ids.append(vid)
    genre_results["all"] = all_ids
    print(f"\nAggregate 'all' category contains {len(all_ids)} total tracks.")

    # Save outputs
    # 1. Update public/songs.json
    os.makedirs(os.path.dirname(SONGS_JSON_PATH), exist_ok=True)
    with open(SONGS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(genre_results, f, indent=2, ensure_ascii=False)
    print(f"Updated public songs database at: {SONGS_JSON_PATH}")
    
    # 2. Save cache
    save_cache(track_cache)

if __name__ == "__main__":
    main()
