import contextlib
import ctypes
import functools
import logging
import logging.handlers
import os
import sys
import threading
import time
from pathlib import Path

import imagegen
import misc
import requests
import spotipy
import winapi
import xxhash
from configuration import AppPaths, ConfigManager
from misc import GenerateNew, SetDefault, SetPrevious, Unchanged, WallpaperAction
from PIL import Image
from PySide6 import QtCore, QtGui, QtWidgets
from spotifyauth import SpotifyAuth
from ui import SystemTrayIcon
from wallpaper import GenerateWallpaper, WindowsWallpaper


class CurrentArt:
    def __init__(self, service: int) -> None:
        if service == 1:  # using lastfm
            self.current_track = self.lastfm_track
        else:
            self.current_track = self.spotify_track
            self.spotify = SpotifyAuth(tray_icon.showMessage)

        self.host_device_name = os.environ["COMPUTERNAME"]

        self.previous_playback_state = None
        self.previously_generated_track = None

    def spotify_track(self) -> GenerateNew | SetDefault | None:
        try:
            self.spotify.refresh_token()
            current = self.spotify.api.current_playback()

            if current["is_playing"] and (
                not ConfigManager.settings["service"]["is_device_specific"]
                or current["device"]["name"] == self.host_device_name
            ):
                return GenerateNew(SpotifyTrack(current))

        except spotipy.client.SpotifyException:  # Token expired
            self.spotify.refresh_token()
        except:  # local tracks, no devices playing  # noqa: E722
            return SetDefault()
        else:  # is_playing is false or not playing on current device
            return SetDefault()

        return Unchanged()

    def lastfm_request(self) -> dict | None:
        try:
            # define headers and URL
            headers = {"user-agent": "AlbumPaper"}
            url = "http://ws.audioscrobbler.com/2.0/"

            payload = {
                "method": "user.getRecentTracks",
                "limit": 1,
                "user": ConfigManager.services["last.fm"]["username"],
                "api_key": ConfigManager.services["last.fm"]["api_key"],
                "format": "json",
            }

            response = requests.get(url, headers=headers, params=payload)  # noqa: S113
            return response.json()
        except:  # noqa: E722
            print("[ERROR] Last.fm request error, setting to default wallpaper")
            return None

    def lastfm_track(self) -> Unchanged | SetDefault | GenerateNew:
        try:
            lastfm_response = self.lastfm_request()
            current = lastfm_response["recenttracks"]["track"][0]
        except (
            KeyError
        ):  # Occurs when last.fm api fails (breifly) or API keys are invalid
            return Unchanged()
        except:  # noqa: E722
            # occurs with poor/no connection
            return SetDefault()

        try:
            if current["@attr"]["nowplaying"].lower() == "true":
                return GenerateNew(LastfmTrack(lastfm_response))

            # when track is not playing
            return SetDefault()
        except:  # occurs when the user isn't playing a track  # noqa: E722
            return SetDefault()

        return Unchanged()

    def current_wallpaper_action(self) -> WallpaperAction:
        wallpaper_action: GenerateNew | SetDefault | Unchanged = self.current_track()

        if wallpaper_action == self.previous_playback_state:
            return Unchanged()

        self.previous_playback_state = wallpaper_action

        match wallpaper_action:
            case SetDefault():
                return SetDefault()
            case Unchanged():
                return Unchanged()

        track: Track = wallpaper_action.track

        if track == self.previously_generated_track:
            return SetPrevious()

        artwork = track.artwork
        if artwork is None:
            return SetDefault()

        self.previously_generated_track = track

        wallpaper_action: GenerateNew

        return wallpaper_action


class Track:
    @property  # image cached via misc.download_image
    def artwork(self) -> Image.Image | None:
        return misc.download_image(self.image_url)

    @property
    def dominant_colors(self) -> list[misc.Color]:
        return imagegen.dominant_colors(self.artwork)


class LastfmTrack(Track):  # noqa: PLW1641
    def __init__(self, response: dict) -> None:
        recent_track = response["recenttracks"]["track"][0]

        self.track_name: str | None = recent_track.get("name")
        self.album_name: str | None = recent_track.get("album", {}).get("#text")
        self.artist_names: str | None = [recent_track.get("artist", {}).get("#text")]
        self.image_url: str = recent_track["image"][0]["#text"].replace(
            "/i/u/34s/",
            "/i/u/600x600/",
        )  # find 600px version

    @property
    def artwork(self) -> Image.Image | None:
        artwork = super().artwork

        missing_art_hash = 3202077406

        if (
            artwork is None
            or xxhash.xxh32(artwork.tobytes("raw")).intdigest() == missing_art_hash
        ):
            return None

        return artwork

    @property
    def spotify_code_image(self) -> None:
        return None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, LastfmTrack):
            return NotImplemented
        return (
            self.track_name == other.track_name and self.album_name == other.album_name
        )


class SpotifyTrack(Track):  # noqa: PLW1641
    def __init__(self, response: dict) -> None:
        item = response["item"]

        self.track_name: str | None = item.get("name")
        self.track_id: str | None = item.get("id")
        self.album_name: str | None = item.get("album", {}).get("name")
        self.album_id: str | None = item.get("album", {}).get("id")
        self.artist_names: list[str] = [
            artist.get("name") for artist in item.get("artists", [])
        ]
        self.artist_ids: list[str] = [
            artist.get("id") for artist in item.get("artists", [])
        ]
        self.image_url: str = item.get("album", {}).get("images", [{}])[0].get("url")

    @functools.cached_property
    def spotify_code_url(self) -> str | None:
        dominant_color = self.dominant_colors[0]
        uri = f"spotify:track:{self.track_id}"

        Y = imagegen.luminance(*dominant_color)  # noqa: N806
        L_star = imagegen.perceived_lightness(Y)  # noqa: N806

        code_color = "white" if L_star < 50 else "black"  # noqa: PLR2004

        r, g, b = dominant_color

        width = ConfigManager.settings["foreground"]["size"]

        min_width = 300
        if width < min_width:
            return None

        width = min(width, 2000)

        return f"https://scannables.scdn.co/uri/plain/png/{r:02x}{g:02x}{b:02x}/{code_color}/{width}/{uri}"

    @property
    def spotify_code_image(self) -> Image.Image | None:
        spotify_code_url = self.spotify_code_url
        if spotify_code_url is None:
            return None
        return misc.download_image(self.spotify_code_url)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SpotifyTrack):
            return NotImplemented
        return self.track_id == other.track_id


class BatterySaverCheckThread(QtCore.QThread):
    # https://stackoverflow.com/a/33150936
    def __init__(self, pause_state_manager) -> None:  # noqa: ANN001
        QtCore.QThread.__init__(self, parent=None)
        self.pause_state_manager = pause_state_manager

    def run(self) -> None:
        try:
            # if disable_on_battery_saver disabled then kill this thread
            if not ConfigManager.settings["power"]["disable_on_battery_saver"]:
                return

            self.sleep = threading.Event()
            battery_saver_enabled_previous = None
            while True:
                battery_saver_enabled = winapi.battery_saver_enabled()
                # To prevent constantly setting desktop to default/generated
                # TODO implement a more elegant solution
                if battery_saver_enabled_previous is not battery_saver_enabled:
                    self.pause_state_manager.set_battery_saver(battery_saver_enabled)

                battery_saver_enabled_previous = battery_saver_enabled
                self.sleep.wait(1)
        except Exception:
            app_log.exception("BatterySaverCheck Error")
            if __debug__:
                raise


class WorkerThread(QtCore.QThread):
    def __init__(self, parent: QtWidgets.QWidget = None) -> None:
        super().__init__(parent)
        self._stop_event = threading.Event()
        self.sleep = threading.Event()
        self.disabled = False

    def run(self) -> None:
        try:
            self._stop_event.clear()

            self._pause_request = ConfigManager.settings["miscellaneous"]["paused"]
            self._battery_saver = (
                winapi.battery_saver_enabled()
                and not ConfigManager.settings["power"]["disable_on_battery_saver"]
            )

            self.disabled = ConfigManager.settings["miscellaneous"]["paused"]

            self.get_art = CurrentArt(
                service=ConfigManager.settings["service"]["option"],
            )

            request_interval = ConfigManager.settings["service"]["request_interval"]

            wallaper_generator = GenerateWallpaper(app)

            while not self._stop_event.is_set():
                if self.disabled:
                    self.sleep.wait(1)
                    continue

                start = time.time()
                wallpaper_action: GenerateNew | SetDefault | Unchanged | SetPrevious = (
                    self.get_art.current_wallpaper_action()
                )
                wallaper_generator.generate(wallpaper_action)

                if isinstance(wallpaper_action, Image.Image):
                    print(f"TOTAL TIME = {(time.time() - start) * 1000:.4g} ms")

                if self._stop_event.wait(request_interval):
                    break

        except Exception:
            app_log.exception("Worker Error")
            if __debug__:
                raise

    def _wait_for_wakeup(self, timeout: float | None = None) -> bool:
        self.sleep.wait(timeout)
        return not self._stop_event.is_set()

    def stop(self) -> None:
        self._stop_event.set()
        self.sleep.set()

    def check_state(self) -> None:
        if self.disabled:
            self.sleep.clear()
            WindowsWallpaper.set_default_wallpaper()
        else:
            with contextlib.suppress(Exception):
                self.sleep.set()
            with contextlib.suppress(AttributeError):
                self.get_art.previous_playback_state = None

            # self.get_art.previously_generated_track = None

    @QtCore.Slot(str)
    def pause_state(self, state: str) -> None:
        if state in ("disabled", "battery_saver"):
            self.disabled = True
        else:
            self.disabled = False
        self.check_state()


class PauseStateSignals(QtCore.QObject):
    pause_state = QtCore.Signal(str)


class PauseStateManager:
    def __init__(self, signal: QtCore.Signal) -> None:
        self.user_pause = ConfigManager.settings["miscellaneous"]["paused"]
        self.battery_saver = False

        mutex = QtCore.QMutex()
        self.locker = QtCore.QMutexLocker(mutex)
        self.signal = signal

    def toggle_pause(self) -> None:
        with self.locker:
            self.user_pause = not self.user_pause
            ConfigManager.settings["miscellaneous"]["paused"] = self.user_pause
            ConfigManager.save_widget_state()
        self.send_signal()

    def set_battery_saver(self, *, enabled: bool) -> None:
        with self.locker:
            self.battery_saver = enabled
        self.send_signal()

    def _state(self) -> str:
        with self.locker:
            if self.battery_saver:
                return "battery_saver"
            if self.user_pause:
                return "disabled"
            return "enabled"

    def send_signal(self) -> None:
        self.signal.pause_state.emit(self._state())


class OnStartup:
    """
    Some methods to run when the program starts
    """

    @staticmethod
    def start_logger() -> logging.Logger:
        try:
            handler = logging.handlers.RotatingFileHandler(
                "errors.log",
                maxBytes=500 * 1024,  # 500 kB
                backupCount=1,
            )
            handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
            handler.setLevel(logging.ERROR)
            app_log = logging.getLogger("root")
            app_log.setLevel(logging.ERROR)
            app_log.addHandler(handler)

        except Exception:
            if __debug__:
                raise

        else:
            return app_log

    @staticmethod
    def start_QApplication() -> QtWidgets.QApplication:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AlbumPaper")
        try:
            app = QtWidgets.QApplication(sys.argv)
        except RuntimeError:  # occurs on restart
            app = QtWidgets.QApplication.instance()

        app.setApplicationName("AlbumPaper")

        app.setQuitOnLastWindowClosed(False)

        return app


RESTART_EXIT_CODE = 1

if __name__ in "__main__":
    exit_code = RESTART_EXIT_CODE
    app_log = OnStartup.start_logger()

    while exit_code == RESTART_EXIT_CODE:
        exit_code = 0
        try:
            Path(AppPaths.DROP_SHADOW).unlink(missing_ok=True)
            cache_images_dir = AppPaths.PYTHON_ROOT / "cache" / "images"
            if not cache_images_dir.exists():
                cache_images_dir.mkdir(parents=True, exist_ok=True)
            if not Path(AppPaths.DEFAULT_WALLPAPER).exists():
                WindowsWallpaper.cache_current()

            app = OnStartup.start_QApplication()

            widget = QtWidgets.QWidget()
            pause_state_signals = PauseStateSignals()

            pause_state_manager = PauseStateManager(pause_state_signals)

            enabled_icon = QtGui.QIcon(
                str(
                    (
                        AppPaths.PYTHON_ROOT / "assets" / "icons" / "enabled.png"
                    ).absolute(),
                ),
            )
            tray_icon = SystemTrayIcon(
                icon=enabled_icon,
                parent=widget,
                signal=pause_state_signals,
                pause_state_manager=pause_state_manager,
            )

            try:
                name = b"AlbumPaper-dev" if __debug__ else b"AlbumPaper"
                mutex = winapi.NamedMutex(name)
            except winapi.MutexNotAquiredError:
                tray_icon.showMessage("App already open", "")
                sys.exit()

            tray_icon.show()

            err_message = ConfigManager.validate_service()

            if err_message:
                tray_icon.showMessage(err_message, "")
                tray_icon.settings_window.show()

            battery_saver_check_thread = BatterySaverCheckThread(
                pause_state_manager,
            )
            battery_saver_check_thread.start(priority=QtCore.QThread.LowestPriority)

            if not err_message:
                worker_thread = WorkerThread()
                pause_state_signals.pause_state.connect(worker_thread.pause_state)
                pause_state_signals.pause_state.connect(tray_icon.pause_state)

                worker_thread.start(priority=QtCore.QThread.LowPriority)

            pause_state_manager.send_signal()

            exit_code = app.exec()

            if not err_message:
                worker_thread.stop()
                worker_thread.wait()

        except Exception:
            app_log.exception("main error")
            if __debug__:
                raise

    mutex.release()
