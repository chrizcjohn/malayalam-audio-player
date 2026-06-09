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

# Configurations
LASTFM_API_URL = "http://ws.audioscrobbler.com/2.0/"
TRACK_LIMIT_PER_TAG = 20 
MAX_NEW_YOUTUBE_SEARCHES = 90 # Safe limit to stay below YouTube's 100 search daily quota limit (1 search = 100 points)

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

# High-quality Curated Malayalam Tracks to seed the database immediately
CURATED_TRACKS = {
    "mollywood": [
        {"title": "Darshana", "artist": "Hesham Abdul Wahab"},
        {"title": "Kudukku", "artist": "Vineeth Sreenivasan"},
        {"title": "Aaradhike", "artist": "Shreya Ghoshal"},
        {"title": "Appangal Embadum", "artist": "Anna Katharina Valayil"},
        {"title": "Lajjavathiye", "artist": "Jassie Gift"},
        {"title": "Kalapakkaara", "artist": "Jakes Bejoy"},
        {"title": "Jaada", "artist": "Sushin Shyam"},
        {"title": "Athiran - Ee Kaattu", "artist": "Sithara Krishnakumar"},
        {"title": "Scene Contra", "artist": "Gopi Sundar"},
        {"title": "Manikya Malaraya Poovi", "artist": "Vineeth Sreenivasan"}
    ],
    "melodies": [
        {"title": "Varamanjalaadiya", "artist": "Sujatha Mohan"},
        {"title": "Anuragha Vilochananayi", "artist": "Shreya Ghoshal"},
        {"title": "Malare", "artist": "Vijay Yesudas"},
        {"title": "Pavizha Mazha", "artist": "K.S. Harisankar"},
        {"title": "Karmukilil", "artist": "K.S. Chithra"},
        {"title": "Aniyathipraavu - Oru Rajamalli", "artist": "Srinivas"},
        {"title": "Jeevamshamayi", "artist": "K.S. Harisankar"},
        {"title": "Mazhaye Mazhaye", "artist": "Haricharan"},
        {"title": "Kamini", "artist": "K.S. Harisankar"},
        {"title": "Oru Pushpam Mathram", "artist": "K.J. Yesudas"}
    ],
    "indie": [
        {"title": "Nada Nada", "artist": "Avial"},
        {"title": "Thaalangal", "artist": "Job Kurian"},
        {"title": "Joy of Little Things", "artist": "When Chai Met Toast"},
        {"title": "Chekele", "artist": "Avial"},
        {"title": "Kantha", "artist": "Masala Coffee"},
        {"title": "Hope", "artist": "Job Kurian"},
        {"title": "Aararo", "artist": "Sooraj Santhosh"},
        {"title": "Navarasam", "artist": "Thaikkudam Bridge"}
    ],
    "hiphop": [
        {"title": "Malabari Banger", "artist": "M.H.R"},
        {"title": "Pani Paali", "artist": "Neeraj Madhav"},
        {"title": "Local Mandan", "artist": "Fejo"},
        {"title": "Kalapila", "artist": "Street Academics"},
        {"title": "Aarada Ath", "artist": "M.H.R"},
        {"title": "Amsham", "artist": "Aksomaniac"},
        {"title": "Chatha", "artist": "Street Academics"}
    ],
    "pop": [
        {"title": "Kudukku", "artist": "Vineeth Sreenivasan"},
        {"title": "Insaanile", "artist": "Jubair Muhammed"},
        {"title": "Appangal Embadum", "artist": "Anna Katharina Valayil"},
        {"title": "Lajjavathiye", "artist": "Jassie Gift"},
        {"title": "Johny Mone", "artist": "Dulquer Salmaan"},
        {"title": "Chundari Penne", "artist": "Dulquer Salmaan"}
    ],
    "rock": [
        {"title": "Nada Nada", "artist": "Avial"},
        {"title": "Chekele", "artist": "Avial"},
        {"title": "Fish Rock", "artist": "Thaikkudam Bridge"},
        {"title": "Karukara", "artist": "Avial"},
        {"title": "Nostalgia Jukebox", "artist": "Thaikkudam Bridge"},
        {"title": "Aadu Pambe", "artist": "Avial"}
    ],
    "folk": [
        {"title": "Chalakudy Chanthayil", "artist": "Kalabhavan Mani"},
        {"title": "Kuttyadi", "artist": "Pradeep Palluruthy"},
        {"title": "Chekele", "artist": "Avial"},
        {"title": "Karthaave", "artist": "Job Kurian"},
        {"title": "Karutha Penne", "artist": "Kalabhavan Mani"}
    ],
    "classics": [
        {"title": "Pramadavanam", "artist": "K.J. Yesudas"},
        {"title": "Rajahamsame", "artist": "K.S. Chithra"},
        {"title": "Harivarasanam", "artist": "K.J. Yesudas"},
        {"title": "Devasabhathalam", "artist": "K.S. Chithra"},
        {"title": "Alliyambal Kadavil", "artist": "K.J. Yesudas"}
    ]
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
        search_response = youtube_client.search().list(
            q=query,
            part="id,snippet",
            maxResults=1,
            type="video",
            videoEmbeddable="true"
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
        print("ERROR: LASTFM_API_KEY or YOUTUBE_API_KEY environment variables are missing.")
        return

    # Initialize YouTube client
    try:
        youtube_client = build("youtube", "v3", developerKey=youtube_key)
    except Exception as e:
        print(f"Failed to build YouTube service client: {e}")
        return

    # Load caches
    track_cache = load_cache()
    genre_results = {}
    search_count = 0
    
    for genre, tags in GENRE_TAGS.items():
        print(f"\nProcessing Genre: {genre.upper()}")
        genre_video_ids = []
        seen_tracks_in_genre = set()
        
        # 1. Merge Curated tracks list with Last.fm scraped list
        tracks_pool = []
        if genre in CURATED_TRACKS:
            tracks_pool.extend(CURATED_TRACKS[genre])
            
        for tag in tags:
            print(f"Fetching Last.fm tag: '{tag}'")
            scraped = get_lastfm_tracks(tag, lastfm_key)
            tracks_pool.extend(scraped)
            
        # 2. Iterate and resolve track video IDs
        for track in tracks_pool:
            track_key = f"{track['artist']} - {track['title']}".lower()
            if track_key in seen_tracks_in_genre:
                continue
            seen_tracks_in_genre.add(track_key)
            
            # Check cache
            if track_key in track_cache:
                cached_id = track_cache[track_key]
                if cached_id: 
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
    
    # 2. Save track cache
    save_cache(track_cache)

if __name__ == "__main__":
    main()
