#!/usr/bin/env python3
import os
import json
import sys
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Force UTF-8 encoding for standard output/error on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# Configurations
TRACKS_PER_GENRE = 80 # Fetch up to 80 tracks per genre (gives ~600+ total songs)

# Playlist search queries for each Malayalam genre
GENRE_PLAYLIST_QUERIES = {
    "mollywood": "latest malayalam movie video songs playlist",
    "melodies": "evergreen malayalam melody songs playlist",
    "indie": "malayalam indie music independent playlist",
    "hiphop": "malayalam hip hop rap songs playlist",
    "pop": "malayalam pop songs new hits playlist",
    "rock": "malayalam rock bands avial thaikkudam bridge playlist",
    "folk": "malayalam naadan paattu traditional folk songs playlist",
    "classics": "malayalam old classics 70s 80s 90s songs playlist"
}

# Resolve paths relative to project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAYLIST_CACHE_PATH = os.path.join(BASE_DIR, "backend", "playlist_cache.json")
SONGS_JSON_PATH = os.path.join(BASE_DIR, "public", "songs.json")

def load_playlist_cache():
    if os.path.exists(PLAYLIST_CACHE_PATH):
        try:
            with open(PLAYLIST_CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading playlist cache: {e}. Starting fresh.")
    return {}

def save_playlist_cache(cache):
    os.makedirs(os.path.dirname(PLAYLIST_CACHE_PATH), exist_ok=True)
    with open(PLAYLIST_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)
    print(f"Saved playlist cache at {PLAYLIST_CACHE_PATH}")

def find_playlist_on_youtube(youtube_client, query):
    try:
        search_response = youtube_client.search().list(
            q=query,
            part="id,snippet",
            maxResults=1,
            type="playlist"
        ).execute()
        
        items = search_response.get("items", [])
        if items:
            playlist_id = items[0]["id"]["playlistId"]
            title = items[0]["snippet"]["title"]
            print(f"YouTube Resolved Playlist for '{query}': '{title}' [{playlist_id}]")
            return playlist_id
        else:
            print(f"YouTube: No playlist found for query: '{query}'")
            return None
    except HttpError as e:
        print(f"YouTube API HttpError searching playlist for '{query}': {e}")
        return None
    except Exception as e:
        print(f"Error searching playlist for '{query}': {e}")
        return None

def fetch_playlist_items(youtube_client, playlist_id, max_results):
    video_ids = []
    next_page_token = None
    
    while len(video_ids) < max_results:
        try:
            # Each list request costs only 1 quota unit and returns up to 50 items
            request = youtube_client.playlistItems().list(
                playlistId=playlist_id,
                part="id,snippet",
                maxResults=min(50, max_results - len(video_ids)),
                pageToken=next_page_token
            )
            response = request.execute()
            
            items = response.get("items", [])
            if not items:
                break
                
            for item in items:
                video_id = item.get("snippet", {}).get("resourceId", {}).get("videoId")
                # Filter out private/deleted videos (usually titled "Deleted video" or "Private video")
                title = item.get("snippet", {}).get("title", "")
                if video_id and "deleted video" not in title.lower() and "private video" not in title.lower():
                    video_ids.append(video_id)
                    
            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break
        except HttpError as e:
            print(f"YouTube API HttpError fetching items for playlist [{playlist_id}]: {e}")
            break
        except Exception as e:
            print(f"Error fetching items for playlist [{playlist_id}]: {e}")
            break
            
    return video_ids

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
    youtube_key = os.environ.get("YOUTUBE_API_KEY")
    
    if not youtube_key:
        print("ERROR: YOUTUBE_API_KEY environment variable is missing.")
        return

    # Initialize YouTube client
    try:
        youtube_client = build("youtube", "v3", developerKey=youtube_key)
    except Exception as e:
        print(f"Failed to build YouTube service client: {e}")
        return

    # Load cache for playlist IDs
    playlist_cache = load_playlist_cache()
    genre_results = {}
    
    for genre, query in GENRE_PLAYLIST_QUERIES.items():
        print(f"\nProcessing Genre: {genre.upper()}")
        playlist_id = None
        
        # Check cache first
        if genre in playlist_cache:
            playlist_id = playlist_cache[genre]
            print(f"Using cached playlist ID for {genre}: [{playlist_id}]")
        else:
            # Search YouTube for the playlist (costs 100 units once)
            playlist_id = find_playlist_on_youtube(youtube_client, query)
            if playlist_id:
                playlist_cache[genre] = playlist_id
                
        if playlist_id:
            # Fetch up to TRACKS_PER_GENRE videos from the playlist (costs 1-2 units)
            video_ids = fetch_playlist_items(youtube_client, playlist_id, TRACKS_PER_GENRE)
            
            # Remove duplicate video IDs
            unique_ids = []
            for vid in video_ids:
                if vid not in unique_ids:
                    unique_ids.append(vid)
            
            genre_results[genre] = unique_ids
            print(f"Genre {genre} populated with {len(unique_ids)} tracks.")
        else:
            genre_results[genre] = []
            print(f"Genre {genre} has 0 tracks (playlist resolution failed).")

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
    
    # 2. Save playlist cache to avoid searching next time
    save_playlist_cache(playlist_cache)

if __name__ == "__main__":
    main()
