"""Synchronized MP3 streaming engine.

Each station has a dedicated broadcaster thread that reads MP3 files from the
playlist at real-time speed.  All connected listeners receive the same audio
frames at the same moment — exactly like traditional radio.

Architecture
------------
StationBroadcaster (one per active station)
    - Runs in a daemon thread
    - Reads MP3 frames from the playlist files sequentially, looping forever
    - Pushes raw MP3 frame data into a shared ring-buffer
    - Tracks the current playing position (track title, artist, elapsed time)

Listener connections
    - Each GET /stream/<slug> opens a long-lived HTTP response
    - The response generator reads from the ring-buffer, starting at the
      current write position (so the listener hears what everyone else hears)
    - If a listener falls behind, it skips ahead to the live position
"""

import os
import sqlite3
import struct
import threading
import time
from collections import deque
from typing import Generator, Optional

from flask import Blueprint, Response, current_app, jsonify

stream_bp = Blueprint("stream", __name__)

# ---------------------------------------------------------------------------
# MP3 frame helpers
# ---------------------------------------------------------------------------

_BITRATE_TABLE = {
    # MPEG-1 Layer III bitrates (kbps), index 0 is "free"
    1: [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0],
    # MPEG-2/2.5 Layer III
    2: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0],
}

_SAMPLERATE_TABLE = {
    0: [44100, 22050, 11025],  # MPEG 2.5
    2: [22050, 11025, 5513],  # MPEG 2  (index 2 in the 2-bit field)
    3: [
        44100,
        22050,
        11025,
    ],  # MPEG 1  (index 3 in the 2-bit field — but standard says 44100/48000/32000)
}

# More accurate MPEG-1 sample rates
_SAMPLERATE_MPEG1 = [44100, 48000, 32000]
_SAMPLERATE_MPEG2 = [22050, 24000, 16000]
_SAMPLERATE_MPEG25 = [11025, 12000, 8000]


def _parse_mp3_frame_header(header_bytes: bytes) -> Optional[tuple[int, float]]:
    """Parse 4-byte MP3 frame header, return (frame_size, duration_sec) or None."""
    if len(header_bytes) < 4:
        return None

    h = struct.unpack(">I", header_bytes)[0]

    # Sync word: 11 bits set
    if (h >> 21) & 0x7FF != 0x7FF:
        return None

    mpeg_version = (h >> 19) & 0x3  # 0=2.5, 1=reserved, 2=2, 3=1
    layer = (h >> 17) & 0x3  # 1=III, 2=II, 3=I
    bitrate_idx = (h >> 12) & 0xF
    samplerate_idx = (h >> 10) & 0x3
    padding = (h >> 9) & 0x1

    if (
        mpeg_version == 1
        or layer == 0
        or bitrate_idx == 0
        or bitrate_idx == 15
        or samplerate_idx == 3
    ):
        return None

    # Only handle Layer III
    if layer != 1:
        return None

    if mpeg_version == 3:
        bitrate = _BITRATE_TABLE[1][bitrate_idx] * 1000
        samplerate = _SAMPLERATE_MPEG1[samplerate_idx]
        samples_per_frame = 1152
    else:
        bitrate = _BITRATE_TABLE[2][bitrate_idx] * 1000
        if mpeg_version == 2:
            samplerate = _SAMPLERATE_MPEG2[samplerate_idx]
        else:
            samplerate = _SAMPLERATE_MPEG25[samplerate_idx]
        samples_per_frame = 576

    if bitrate == 0 or samplerate == 0:
        return None

    frame_size = (samples_per_frame * bitrate) // (8 * samplerate) + padding
    duration = samples_per_frame / samplerate

    return frame_size, duration


def _iter_mp3_frames(filepath: str) -> Generator[tuple[bytes, float], None, None]:
    """Yield (frame_bytes, frame_duration_sec) for each MP3 frame in a file."""
    with open(filepath, "rb") as f:
        data = f.read()

    pos = 0
    length = len(data)

    # Skip ID3v2 tag if present
    if length >= 10 and data[:3] == b"ID3":
        tag_size = (
            (data[6] & 0x7F) << 21
            | (data[7] & 0x7F) << 14
            | (data[8] & 0x7F) << 7
            | (data[9] & 0x7F)
        )
        pos = 10 + tag_size

    while pos < length - 4:
        # Look for sync word
        if data[pos] != 0xFF or (data[pos + 1] & 0xE0) != 0xE0:
            pos += 1
            continue

        result = _parse_mp3_frame_header(data[pos : pos + 4])
        if result is None:
            pos += 1
            continue

        frame_size, duration = result
        if pos + frame_size > length:
            break

        yield data[pos : pos + frame_size], duration
        pos += frame_size


# ---------------------------------------------------------------------------
# Ring buffer for broadcasting
# ---------------------------------------------------------------------------

_RING_SIZE = 2048  # number of chunks to keep in memory


class RingBuffer:
    """Thread-safe ring buffer that stores recent MP3 frame chunks."""

    def __init__(self, max_size: int = _RING_SIZE) -> None:
        self.buffer: deque[bytes] = deque(maxlen=max_size)
        self.write_pos: int = 0
        self.lock = threading.Lock()
        self.event = threading.Event()

    def write(self, data: bytes) -> int:
        """Append a chunk and return its sequence number."""
        with self.lock:
            self.buffer.append(data)
            seq = self.write_pos
            self.write_pos += 1
        self.event.set()
        self.event.clear()
        return seq

    def read_from(self, seq: int) -> tuple[Optional[bytes], int]:
        """Read chunk at *seq*. Returns (data, next_seq) or (None, current_seq) if not yet available."""
        with self.lock:
            oldest = self.write_pos - len(self.buffer)
            if seq < oldest:
                # Listener fell behind — skip to live
                seq = self.write_pos - 1 if self.write_pos > 0 else 0
            if seq >= self.write_pos:
                return None, seq
            idx = seq - oldest
            if idx < 0 or idx >= len(self.buffer):
                return None, self.write_pos
            return self.buffer[idx], seq + 1

    def wait(self, timeout: float = 1.0) -> None:
        """Block until new data is written or timeout."""
        self.event.wait(timeout)


# ---------------------------------------------------------------------------
# Station broadcaster
# ---------------------------------------------------------------------------


class NowPlaying:
    """Current track info for a station."""

    def __init__(self) -> None:
        self.title: str = ""
        self.artist: str = ""
        self.station_name: str = ""
        self.started_at: float = 0.0
        self.duration: float = 0.0
        self.lock = threading.Lock()

    def update(
        self, title: str, artist: str, station_name: str, duration: float
    ) -> None:
        with self.lock:
            self.title = title
            self.artist = artist
            self.station_name = station_name
            self.started_at = time.time()
            self.duration = duration

    def to_dict(self) -> dict[str, object]:
        with self.lock:
            elapsed = time.time() - self.started_at if self.started_at else 0
            return {
                "title": self.title,
                "artist": self.artist,
                "station": self.station_name,
                "elapsed": round(elapsed, 1),
                "duration": round(self.duration, 1),
            }


class StationBroadcaster:
    """Background thread that streams a station's playlist in real time."""

    def __init__(
        self, station_id: int, station_name: str, db_path: str, upload_folder: str
    ) -> None:
        self.station_id = station_id
        self.station_name = station_name
        self.db_path = db_path
        self.upload_folder = upload_folder
        self.ring = RingBuffer()
        self.now_playing = NowPlaying()
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name=f"radio-{station_id}"
        )
        self.listener_count = 0
        self.listener_lock = threading.Lock()

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _get_playlist(self) -> list[dict[str, object]]:
        """Fetch the ordered track list from the database."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT title, artist, filename, duration FROM tracks "
            "WHERE station_id = ? ORDER BY sort_order",
            (self.station_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def _run(self) -> None:
        """Main broadcast loop — plays tracks sequentially, loops forever."""
        while not self._stop.is_set():
            playlist = self._get_playlist()
            if not playlist:
                # No tracks — send silence / wait and retry
                self.now_playing.update("Нет треков", "", self.station_name, 0)
                # Generate a short silence frame (valid MP3 frame of silence)
                self._stop.wait(5.0)
                continue

            for track in playlist:
                if self._stop.is_set():
                    return

                filepath = os.path.join(self.upload_folder, str(track["filename"]))
                if not os.path.exists(filepath):
                    continue

                self.now_playing.update(
                    str(track["title"]),
                    str(track["artist"]),
                    self.station_name,
                    float(track["duration"]),  # type: ignore[arg-type]
                )

                # Stream MP3 frames at real-time pace
                for frame_data, frame_duration in _iter_mp3_frames(filepath):
                    if self._stop.is_set():
                        return
                    self.ring.write(frame_data)
                    # Sleep for the frame's duration to maintain real-time playback
                    time.sleep(frame_duration)


# ---------------------------------------------------------------------------
# Global broadcaster registry
# ---------------------------------------------------------------------------

_broadcasters: dict[str, StationBroadcaster] = {}
_broadcasters_lock = threading.Lock()


def _get_or_create_broadcaster(
    slug: str, app_config: dict[str, object]
) -> Optional[StationBroadcaster]:
    """Return the broadcaster for *slug*, creating it on first access."""
    with _broadcasters_lock:
        if slug in _broadcasters:
            return _broadcasters[slug]

    # Look up station in DB
    db_path = str(app_config["DATABASE_PATH"])
    upload_folder = str(app_config["UPLOAD_FOLDER"])

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT id, name FROM stations WHERE slug = ? AND is_active = 1", (slug,)
    ).fetchone()
    conn.close()

    if row is None:
        return None

    with _broadcasters_lock:
        # Double-check after acquiring lock
        if slug in _broadcasters:
            return _broadcasters[slug]

        broadcaster = StationBroadcaster(
            station_id=row["id"],
            station_name=row["name"],
            db_path=db_path,
            upload_folder=upload_folder,
        )
        broadcaster.start()
        _broadcasters[slug] = broadcaster
        return broadcaster


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@stream_bp.route("/health")
def health() -> str:
    return "ok"


@stream_bp.route("/<slug>")
def listen(slug: str) -> Response:
    """Long-lived MP3 stream for a station. All listeners hear the same audio."""
    config = dict(current_app.config)
    broadcaster = _get_or_create_broadcaster(slug, config)
    if broadcaster is None:
        return Response("Station not found", status=404)

    def generate() -> Generator[bytes, None, None]:
        seq = broadcaster.ring.write_pos  # start from live position
        with broadcaster.listener_lock:
            broadcaster.listener_count += 1
        try:
            while True:
                data, seq = broadcaster.ring.read_from(seq)
                if data is not None:
                    yield data
                else:
                    broadcaster.ring.wait(timeout=1.0)
        except GeneratorExit:
            pass
        finally:
            with broadcaster.listener_lock:
                broadcaster.listener_count -= 1

    return Response(
        generate(),
        mimetype="audio/mpeg",
        headers={
            "Cache-Control": "no-cache, no-store",
            "Connection": "keep-alive",
            "X-Content-Type-Options": "nosniff",
            "Icy-Name": slug,
        },
    )


@stream_bp.route("/<slug>/now-playing")
def now_playing(slug: str) -> Response:
    """Return JSON with current track info for a station."""
    config = dict(current_app.config)
    broadcaster = _get_or_create_broadcaster(slug, config)
    if broadcaster is None:
        return jsonify({"error": "Station not found"}), 404  # type: ignore[return-value]

    info = broadcaster.now_playing.to_dict()
    with broadcaster.listener_lock:
        info["listeners"] = broadcaster.listener_count
    return jsonify(info)


@stream_bp.route("/stations/status")
def stations_status() -> Response:
    """Return JSON status of all active broadcasters."""
    result = []
    with _broadcasters_lock:
        for slug, bc in _broadcasters.items():
            info = bc.now_playing.to_dict()
            with bc.listener_lock:
                info["listeners"] = bc.listener_count
            info["slug"] = slug
            result.append(info)
    return jsonify(result)
