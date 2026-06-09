// Malayalam Music Randomizer Client Logic
import './style.css';

// State Management
let songsData = null;
let currentGenre = 'all';
let currentVideoId = null;
let player = null;
let isMuted = false;
let savedVolume = 80;

// History Tracking
const playHistory = [];
const recentTracks = new Set(); // Tracks to avoid playing again too soon
const MAX_RECENT_TRACKS = 8; // Number of tracks to remember to avoid immediate repeats

// DOM Elements
const btnPlayPause = document.getElementById('btn-play-pause');
const btnNext = document.getElementById('btn-next');
const btnPrev = document.getElementById('btn-prev');
const btnMute = document.getElementById('btn-mute');
const volumeSlider = document.getElementById('volume-slider');
const volumeIconHigh = document.getElementById('volume-icon-high');
const volumeIconMute = document.getElementById('volume-icon-mute');
const songTitle = document.getElementById('song-title');
const songArtist = document.getElementById('song-artist');
const visualizer = document.getElementById('visualizer-wrapper');
const playerOverlay = document.getElementById('player-overlay');
const overlayText = document.getElementById('overlay-text');
const genreGrid = document.getElementById('genre-grid');

// 1. Fetch Songs Database
async function initSongsData() {
    try {
        updateOverlay('Loading playlist database...');
        const response = await fetch('/songs.json');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        songsData = await response.json();
        
        // Ensure "all" is populated if not present
        if (!songsData.all) {
            const allIds = new Set();
            Object.keys(songsData).forEach(genre => {
                songsData[genre].forEach(id => allIds.add(id));
            });
            songsData.all = Array.from(allIds);
        }
        
        updateOverlay('Playlist loaded. Loading player...');
        loadYouTubePlayerAPI();
    } catch (error) {
        console.error('Failed to load songs.json:', error);
        updateOverlay('Failed to load songs database. Please try reloading.');
    }
}

// 2. Load YouTube API
function loadYouTubePlayerAPI() {
    // Inject the YouTube Iframe Player API script
    const tag = document.createElement('script');
    tag.src = "https://www.youtube.com/iframe_api";
    const firstScriptTag = document.getElementsByTagName('script')[0];
    firstScriptTag.parentNode.insertBefore(tag, firstScriptTag);
}

// Global Callback required by YT API
window.onYouTubeIframeAPIReady = function() {
    updateOverlay('Initializing player...');
    player = new YT.Player('yt-player', {
        height: '100%',
        width: '100%',
        playerVars: {
            'autoplay': 0,
            'controls': 0, // Disable native controls
            'disablekb': 1,
            'fs': 0,
            'modestbranding': 1,
            'rel': 0,
            'showinfo': 0,
            'iv_load_policy': 3,
            'origin': window.location.origin
        },
        events: {
            'onReady': onPlayerReady,
            'onStateChange': onPlayerStateChange,
            'onError': onPlayerError
        }
    });
};

// 3. Player Event Handlers
function onPlayerReady(event) {
    updateOverlay('Ready to Play');
    // Hide overlay after a slight delay
    setTimeout(() => {
        playerOverlay.classList.add('hidden');
    }, 600);
    
    // Set initial volume
    player.setVolume(savedVolume);
    volumeSlider.value = savedVolume;
    
    // Select initial song but do not autoplay immediately to respect browser policies
    selectRandomSong(false);
}

function onPlayerStateChange(event) {
    // States: -1 (unstarted), 0 (ended), 1 (playing), 2 (paused), 3 (buffering), 5 (video cued)
    switch(event.data) {
        case YT.PlayerState.PLAYING:
            playerOverlay.classList.add('hidden');
            btnPlayPause.querySelector('.play-icon').classList.add('hidden');
            btnPlayPause.querySelector('.pause-icon').classList.remove('hidden');
            visualizer.classList.add('active');
            updateSongInfo();
            break;
            
        case YT.PlayerState.PAUSED:
            btnPlayPause.querySelector('.play-icon').classList.remove('hidden');
            btnPlayPause.querySelector('.pause-icon').classList.add('hidden');
            visualizer.classList.remove('active');
            break;
            
        case YT.PlayerState.BUFFERING:
            updateOverlay('Buffering...', false);
            break;
            
        case YT.PlayerState.ENDED:
            // Auto-advance to next random track
            playNextTrack();
            break;
            
        case YT.PlayerState.CUED:
            visualizer.classList.remove('active');
            btnPlayPause.querySelector('.play-icon').classList.remove('hidden');
            btnPlayPause.querySelector('.pause-icon').classList.add('hidden');
            break;
    }
}

function onPlayerError(event) {
    console.error('YouTube Player Error:', event.data);
    // Common errors: 2 (invalid parameter), 100 (video not found/removed), 101/150 (embed restricted)
    let errorMsg = 'Error loading video';
    if (event.data === 100 || event.data === 101 || event.data === 150) {
        errorMsg = 'Video unavailable. Skipping...';
    }
    
    updateOverlay(errorMsg, false);
    
    // Auto skip after 2.5 seconds
    setTimeout(() => {
        playNextTrack();
    }, 2500);
}

// Update UI Text Info dynamically from YouTube API
function updateSongInfo() {
    if (player && typeof player.getVideoData === 'function') {
        const videoData = player.getVideoData();
        if (videoData && videoData.title) {
            songTitle.textContent = videoData.title;
            // Clean up author (if YouTube channel has 'Official' or similar, we can present clean layout)
            songArtist.textContent = videoData.author || 'Official YouTube Stream';
            return;
        }
    }
    songTitle.textContent = 'Playing track...';
    songArtist.textContent = 'Official YouTube Stream';
}

// 4. Track Navigation & Randomizer Logic
function selectRandomSong(autoplay = true) {
    if (!songsData || !songsData[currentGenre]) return;
    
    const songIds = songsData[currentGenre];
    if (songIds.length === 0) {
        songTitle.textContent = 'No tracks available';
        songArtist.textContent = 'Add tracks to this genre tag';
        return;
    }
    
    // Filter out recently played tracks to maintain diversity
    let availableSongs = songIds.filter(id => !recentTracks.has(id));
    
    // If all available tracks are recently played, reset the list
    if (availableSongs.length === 0) {
        recentTracks.clear();
        availableSongs = songIds;
    }
    
    // If there is only one track, just play it
    let chosenId = null;
    if (availableSongs.length === 1) {
        chosenId = availableSongs[0];
    } else {
        // Exclude the current song if possible, unless it's the only one left
        let selectionPool = availableSongs.filter(id => id !== currentVideoId);
        if (selectionPool.length === 0) selectionPool = availableSongs;
        
        const randomIndex = Math.floor(Math.random() * selectionPool.length);
        chosenId = selectionPool[randomIndex];
    }
    
    if (chosenId) {
        playSong(chosenId, autoplay);
    }
}

function playSong(videoId, autoplay = true) {
    if (!player) return;
    
    // Push previous to history
    if (currentVideoId && currentVideoId !== videoId) {
        playHistory.push(currentVideoId);
        btnPrev.removeAttribute('disabled');
    }
    
    currentVideoId = videoId;
    recentTracks.add(videoId);
    
    // Keep set size bounded
    if (recentTracks.size > MAX_RECENT_TRACKS) {
        const firstAdded = recentTracks.values().next().value;
        recentTracks.delete(firstAdded);
    }
    
    // Show spinner overlay
    updateOverlay('Loading video...');
    
    // Load and play/cue video
    if (autoplay) {
        player.loadVideoById(videoId);
    } else {
        player.cueVideoById(videoId);
        // Display placeholder info until played
        songTitle.textContent = 'Ready to Play';
        songArtist.textContent = 'Press play or choose next song';
    }
}

function playNextTrack() {
    selectRandomSong(true);
}

function playPrevTrack() {
    if (playHistory.length === 0) return;
    
    const prevId = playHistory.pop();
    currentVideoId = prevId;
    
    if (playHistory.length === 0) {
        btnPrev.setAttribute('disabled', 'true');
    }
    
    updateOverlay('Loading video...');
    player.loadVideoById(prevId);
}

// 5. Helper UI Functions
function updateOverlay(text, showSpinner = true) {
    overlayText.textContent = text;
    const spinner = playerOverlay.querySelector('.overlay-spinner');
    if (showSpinner) {
        spinner.classList.remove('hidden');
    } else {
        spinner.classList.add('hidden');
    }
    playerOverlay.classList.remove('hidden');
}

// 6. Event Listeners Setup
function setupControls() {
    // Play/Pause
    btnPlayPause.addEventListener('click', () => {
        if (!player) return;
        const state = player.getPlayerState();
        if (state === YT.PlayerState.PLAYING) {
            player.pauseVideo();
        } else {
            player.playVideo();
        }
    });

    // Next/Prev Buttons
    btnNext.addEventListener('click', playNextTrack);
    btnPrev.addEventListener('click', playPrevTrack);

    // Mute button click
    btnMute.addEventListener('click', () => {
        if (!player) return;
        isMuted = !isMuted;
        if (isMuted) {
            player.mute();
            volumeIconHigh.classList.add('hidden');
            volumeIconMute.classList.remove('hidden');
        } else {
            player.unmute();
            volumeIconHigh.classList.remove('hidden');
            volumeIconMute.classList.add('hidden');
        }
    });

    // Volume Slider input
    volumeSlider.addEventListener('input', (e) => {
        const volumeVal = parseInt(e.target.value);
        savedVolume = volumeVal;
        if (player) {
            player.setVolume(volumeVal);
            if (volumeVal === 0) {
                player.mute();
                isMuted = true;
                volumeIconHigh.classList.add('hidden');
                volumeIconMute.classList.remove('hidden');
            } else {
                player.unmute();
                isMuted = false;
                volumeIconHigh.classList.remove('hidden');
                volumeIconMute.classList.add('hidden');
            }
        }
    });

    // Genre pill click events
    genreGrid.addEventListener('click', (e) => {
        const targetPill = e.target.closest('.genre-pill');
        if (!targetPill) return;
        
        // Remove active class from all pills
        const pills = genreGrid.querySelectorAll('.genre-pill');
        pills.forEach(pill => pill.classList.remove('active'));
        
        // Add active to selected pill
        targetPill.classList.add('active');
        
        // Update genre
        const newGenre = targetPill.dataset.genre;
        if (newGenre !== currentGenre) {
            currentGenre = newGenre;
            recentTracks.clear(); // Clear recent tracks on genre switch to avoid starvation
            selectRandomSong(true);
        }
    });
}

// 7. Initial Entry Point
document.addEventListener('DOMContentLoaded', () => {
    setupControls();
    initSongsData();
});
