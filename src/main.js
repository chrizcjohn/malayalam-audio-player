// Malayalam Music Randomizer Client Logic
import './style.css';

// State Management
let songsData = null;
let currentGenre = 'all';
let currentVideoId = null;
let player = null;
let isMuted = false;
let savedVolume = 80;
let autoplayEnabled = true;
let progressInterval = null;
let isSeeking = false;

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
const autoplayToggle = document.getElementById('autoplay-toggle');
const playlistList = document.getElementById('playlist-list');
const playlistCount = document.getElementById('playlist-count');
const playlistContainer = document.getElementById('playlist-container');
const progressSlider = document.getElementById('progress-slider');
const timeElapsed = document.getElementById('time-elapsed');
const timeDuration = document.getElementById('time-duration');

// 1. Fetch Songs Database
async function initSongsData() {
    try {
        updateOverlay('Loading playlist database...');
        const response = await fetch('songs.json');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        songsData = await response.json();
        
        // Ensure "all" is populated if not present
        if (!songsData.all) {
            const allTracks = [];
            const seenIds = new Set();
            Object.keys(songsData).forEach(genre => {
                songsData[genre].forEach(track => {
                    if (!seenIds.has(track.id)) {
                        seenIds.add(track.id);
                        allTracks.push(track);
                    }
                });
            });
            songsData.all = allTracks;
        }
        
        updateOverlay('Playlist loaded. Loading player...');
        renderPlaylist();
        loadYouTubePlayerAPI();
    } catch (error) {
        console.error('Failed to load songs.json:', error);
        updateOverlay('Failed to load songs database. Please try reloading.');
    }
}

// Render playlist scroll list
function renderPlaylist() {
    if (!songsData || !songsData[currentGenre]) return;
    
    playlistList.innerHTML = '';
    const tracks = songsData[currentGenre];
    playlistCount.textContent = tracks.length;
    
    if (tracks.length === 0) {
        playlistList.innerHTML = '<li class="playlist-placeholder">No tracks available in this genre.</li>';
        return;
    }
    
    tracks.forEach((track, index) => {
        const li = document.createElement('li');
        li.className = 'playlist-item';
        li.dataset.id = track.id;
        
        // Mark active if playing
        if (track.id === currentVideoId) {
            li.classList.add('active');
        }
        
        li.innerHTML = `
            <span class="playlist-item-num">${index + 1}</span>
            <div class="playlist-item-details">
                <div class="playlist-item-title" title="${track.title}">${track.title}</div>
                <div class="playlist-item-artist">${track.artist}</div>
            </div>
        `;
        
        li.addEventListener('click', () => {
            playSong(track.id, true);
        });
        
        playlistList.appendChild(li);
    });
    
    highlightCurrentTrack(false); // Highlight and scroll without force
}

// Highlight currently playing track in playlist
function highlightCurrentTrack(scrollIntoView = true) {
    const items = playlistList.querySelectorAll('.playlist-item');
    items.forEach(item => {
        if (item.dataset.id === currentVideoId) {
            item.classList.add('active');
            if (scrollIntoView) {
                item.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        } else {
            item.classList.remove('active');
        }
    });
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
            highlightCurrentTrack(true);
            startProgressTracker();
            break;
            
        case YT.PlayerState.PAUSED:
            btnPlayPause.querySelector('.play-icon').classList.remove('hidden');
            btnPlayPause.querySelector('.pause-icon').classList.add('hidden');
            visualizer.classList.remove('active');
            stopProgressTracker();
            break;
            
        case YT.PlayerState.BUFFERING:
            updateOverlay('Buffering...', false);
            break;
            
        case YT.PlayerState.ENDED:
            stopProgressTracker();
            resetProgressBar();
            // Auto-advance to next random track if autoplay is enabled
            if (autoplayEnabled) {
                playNextTrack();
            } else {
                btnPlayPause.querySelector('.play-icon').classList.remove('hidden');
                btnPlayPause.querySelector('.pause-icon').classList.add('hidden');
                visualizer.classList.remove('active');
                updateOverlay('Track Finished', false);
            }
            break;
            
        case YT.PlayerState.CUED:
            visualizer.classList.remove('active');
            btnPlayPause.querySelector('.play-icon').classList.remove('hidden');
            btnPlayPause.querySelector('.pause-icon').classList.add('hidden');
            stopProgressTracker();
            resetProgressBar();
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
    
    const tracks = songsData[currentGenre];
    if (tracks.length === 0) {
        songTitle.textContent = 'No tracks available';
        songArtist.textContent = 'Add tracks to this genre tag';
        return;
    }
    
    // Filter out recently played tracks to maintain diversity
    let availableSongs = tracks.filter(t => !recentTracks.has(t.id));
    
    // If all available tracks are recently played, reset the list
    if (availableSongs.length === 0) {
        recentTracks.clear();
        availableSongs = tracks;
    }
    
    // If there is only one track, just play it
    let chosenTrack = null;
    if (availableSongs.length === 1) {
        chosenTrack = availableSongs[0];
    } else {
        // Exclude the current song if possible, unless it's the only one left
        let selectionPool = availableSongs.filter(t => t.id !== currentVideoId);
        if (selectionPool.length === 0) selectionPool = availableSongs;
        
        const randomIndex = Math.floor(Math.random() * selectionPool.length);
        chosenTrack = selectionPool[randomIndex];
    }
    
    if (chosenTrack) {
        playSong(chosenTrack.id, autoplay);
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
    
    // Highlight track in playlist
    highlightCurrentTrack(true);
    
    // Show spinner overlay
    updateOverlay('Loading video...');
    
    // Load and play/cue video
    if (autoplay) {
        player.loadVideoById(videoId);
    } else {
        player.cueVideoById(videoId);
        // Find metadata locally to display instantly
        const tracks = songsData[currentGenre] || [];
        const currentTrack = tracks.find(t => t.id === videoId);
        if (currentTrack) {
            songTitle.textContent = currentTrack.title;
            songArtist.textContent = currentTrack.artist;
        } else {
            songTitle.textContent = 'Ready to Play';
            songArtist.textContent = 'Press play or choose next song';
        }
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

function formatTime(seconds) {
    if (isNaN(seconds) || seconds === undefined || seconds === null) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function startProgressTracker() {
    if (progressInterval) clearInterval(progressInterval);
    progressInterval = setInterval(updateProgressBar, 500);
}

function stopProgressTracker() {
    if (progressInterval) {
        clearInterval(progressInterval);
        progressInterval = null;
    }
}

function updateProgressBar() {
    if (!player || typeof player.getCurrentTime !== 'function' || isSeeking) return;
    
    try {
        const currentTime = player.getCurrentTime();
        const duration = player.getDuration();
        
        if (duration && duration > 0) {
            progressSlider.max = Math.floor(duration);
            progressSlider.value = Math.floor(currentTime);
            timeElapsed.textContent = formatTime(currentTime);
            timeDuration.textContent = formatTime(duration);
            
            // Highlight background gradient
            const percentage = (currentTime / duration) * 100;
            progressSlider.style.background = `linear-gradient(to right, hsl(150, 80%, 50%) ${percentage}%, rgba(255, 255, 255, 0.1) ${percentage}%)`;
        } else {
            resetProgressBar();
        }
    } catch (e) {
        console.error("Error updating progress bar", e);
    }
}

function resetProgressBar() {
    progressSlider.value = 0;
    progressSlider.max = 100;
    timeElapsed.textContent = '0:00';
    timeDuration.textContent = '0:00';
    progressSlider.style.background = 'rgba(255, 255, 255, 0.1)';
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

    // Autoplay toggle change
    autoplayToggle.addEventListener('change', () => {
        autoplayEnabled = autoplayToggle.checked;
    });

    // Playback Progress Slider events
    progressSlider.addEventListener('input', (e) => {
        isSeeking = true;
        const seekValue = parseInt(e.target.value);
        timeElapsed.textContent = formatTime(seekValue);
        
        const max = parseInt(progressSlider.max) || 100;
        const percentage = (seekValue / max) * 100;
        progressSlider.style.background = `linear-gradient(to right, hsl(150, 80%, 50%) ${percentage}%, rgba(255, 255, 255, 0.1) ${percentage}%)`;
    });

    progressSlider.addEventListener('change', (e) => {
        if (player && typeof player.seekTo === 'function') {
            const seekValue = parseInt(e.target.value);
            player.seekTo(seekValue, true);
        }
        isSeeking = false;
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
            renderPlaylist(); // Render new playlist
            
            // Auto play or cue initial song depending on autoplay toggle state
            selectRandomSong(autoplayEnabled);
        }
    });
}

// 7. Initial Entry Point
document.addEventListener('DOMContentLoaded', () => {
    setupControls();
    initSongsData();
});
