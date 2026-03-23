/**
 * Online Radio Player — synchronized streaming client.
 *
 * All listeners hear the same audio because the server streams MP3 frames
 * at real-time pace from a shared ring buffer.
 */

(function () {
    "use strict";

    // DOM elements
    const audio = document.getElementById("radio-audio");
    const playerBar = document.getElementById("player-bar");
    const btnPlay = document.getElementById("btn-play");
    const btnStop = document.getElementById("btn-stop");
    const stationName = document.getElementById("player-station-name");
    const trackInfo = document.getElementById("player-track-info");
    const volumeSlider = document.getElementById("volume-slider");
    const volumeValue = document.getElementById("volume-value");
    const volumeIcon = document.getElementById("volume-icon");
    const listenerCount = document.getElementById("listener-count");

    let currentSlug = null;
    let nowPlayingInterval = null;

    // ---- Volume ----

    function setVolume(val) {
        audio.volume = val / 100;
        volumeValue.textContent = val + "%";
        if (val === 0) {
            volumeIcon.innerHTML = "&#128263;";
        } else if (val < 50) {
            volumeIcon.innerHTML = "&#128265;";
        } else {
            volumeIcon.innerHTML = "&#128266;";
        }
    }

    volumeSlider.addEventListener("input", function () {
        setVolume(parseInt(this.value, 10));
    });

    volumeIcon.addEventListener("click", function () {
        if (audio.volume > 0) {
            volumeSlider.dataset.prev = volumeSlider.value;
            volumeSlider.value = 0;
            setVolume(0);
        } else {
            var prev = parseInt(volumeSlider.dataset.prev || "80", 10);
            volumeSlider.value = prev;
            setVolume(prev);
        }
    });

    setVolume(80);

    // ---- Playback ----

    function play(slug, name) {
        // Stop previous stream
        stop();

        currentSlug = slug;
        stationName.textContent = name;
        trackInfo.textContent = "Подключение...";
        playerBar.style.display = "block";

        // Set stream URL — the server sends a continuous MP3 stream
        audio.src = "/stream/" + slug;
        audio.load();
        audio.play().catch(function () {
            trackInfo.textContent = "Нажмите Play для воспроизведения";
        });

        btnPlay.style.display = "none";
        btnStop.style.display = "inline-flex";

        // Highlight active station card
        document.querySelectorAll(".station-card").forEach(function (card) {
            card.classList.remove("playing");
            if (card.dataset.slug === slug) {
                card.classList.add("playing");
            }
        });

        // Start polling now-playing info
        fetchNowPlaying();
        nowPlayingInterval = setInterval(fetchNowPlaying, 3000);
    }

    function stop() {
        audio.pause();
        audio.removeAttribute("src");
        audio.load();

        currentSlug = null;
        btnPlay.style.display = "inline-flex";
        btnStop.style.display = "none";
        trackInfo.textContent = "Остановлено";

        document.querySelectorAll(".station-card.playing").forEach(function (card) {
            card.classList.remove("playing");
        });

        if (nowPlayingInterval) {
            clearInterval(nowPlayingInterval);
            nowPlayingInterval = null;
        }
    }

    function fetchNowPlaying() {
        if (!currentSlug) return;

        fetch("/stream/" + currentSlug + "/now-playing")
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (data.title) {
                    var text = data.title;
                    if (data.artist) {
                        text = data.artist + " — " + data.title;
                    }
                    trackInfo.textContent = text;
                }
                if (typeof data.listeners === "number") {
                    listenerCount.textContent = data.listeners;
                }
            })
            .catch(function () {
                // Silently ignore fetch errors
            });
    }

    // ---- Event listeners ----

    btnPlay.addEventListener("click", function () {
        if (currentSlug) {
            audio.play().catch(function () {});
            btnPlay.style.display = "none";
            btnStop.style.display = "inline-flex";
        }
    });

    btnStop.addEventListener("click", stop);

    // Station play buttons (on cards and detail page)
    document.addEventListener("click", function (e) {
        var btn = e.target.closest(".station-play-btn");
        if (btn) {
            e.preventDefault();
            e.stopPropagation();
            play(btn.dataset.slug, btn.dataset.name);
        }
    });

    // Clicking a station card also starts playback
    document.addEventListener("click", function (e) {
        var card = e.target.closest(".station-card");
        if (card && !e.target.closest(".station-play-btn")) {
            play(card.dataset.slug, card.dataset.name);
        }
    });

    // Handle audio errors gracefully
    audio.addEventListener("error", function () {
        trackInfo.textContent = "Ошибка воспроизведения. Попробуйте снова.";
        btnPlay.style.display = "inline-flex";
        btnStop.style.display = "none";
    });

    // When audio starts playing
    audio.addEventListener("playing", function () {
        if (trackInfo.textContent === "Подключение...") {
            trackInfo.textContent = "В эфире";
        }
    });

})();
