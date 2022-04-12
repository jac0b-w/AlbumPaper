# external imports
import os, sys, spotipy, requests, logging, logging.handlers, threading, pkg_resources
from PySide2 import QtWidgets, QtGui, QtCore
from PIL import Image, ImageChops
from io import BytesIO

# In this directory
from ui import SystemTrayIcon, SettingsWindow
from config import ConfigManager, ConfigValidationError
from wallpaper import Wallpaper, GenerateWallpaper
from spotifyauth import SpotifyAuth
import winapi

VERSION = "v4.0-beta.2"  # as tagged on github

"""
Displays a toast message if a new release is detected
"""


def check_for_updates(tray_icon):
    if not ConfigManager.settings["updates"]["check_for_updates"]:
        return

    try:
        response = requests.get(
            "https://api.github.com/repos/jac0b-w/AlbumPaper/releases/latest"
        )
        latest_version: str = response.json()["tag_name"]
    except Exception:
        return
    if any(substring in latest_version for substring in ["alpha", "beta"]):
        return

    if pkg_resources.parse_version(VERSION) < pkg_resources.parse_version(
        latest_version
    ):
        tray_icon.showMessage("New update", f"Update {latest_version} avaliable")


class CurrentArt:
    def __init__(self, service: str):
        if service == "last.fm":  # using lastfm
            self.art_url = self.lastfm_art_url
        else:
            self.art_url = self.spotify_art_url
            self.spotify = SpotifyAuth(tray_icon.showMessage)

        self.missing_art = Image.open("assets/missing_art.jpg").convert("RGB")
        self.previous_image_url = None
        self.previously_generated_url = None

    def spotify_art_url(self) -> str:
        try:
            self.spotify.refresh_token()
            current = self.spotify.api.currently_playing()
            if current["is_playing"]:
                return current["item"]["album"]["images"][0]["url"]
            else:
                return "default"
        except spotipy.client.SpotifyException:  # Token expired
            self.spotify.refresh_token()
        except:  # local tracks, no devices playing
            return "default"

    def lastfm_request(self):
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

            response = requests.get(url, headers=headers, params=payload)
            return response.json()
        except:
            print("[ERROR] Last.fm request error")
            return None

    def lastfm_art_url(self):
        try:
            current = self.lastfm_request()["recenttracks"]["track"][0]
        except KeyError:  # Occurs when last.fm api fails (breifly) or API keys are invalid
            return None
        except:
            # occurs with poor/no connection
            return "default"
        try:
            if current["@attr"]["nowplaying"].lower() == "true":
                return current["image"][0]["#text"].replace(
                    "/i/u/34s/", "/i/u/600x600/"
                )  # find 600px version
            else:  # when track is not playing
                return "default"
        except:  # occurs when the user isn't playing a track
            return "default"

    @staticmethod
    def download_image(url: str) -> Image.Image:
        response = requests.get(url)
        return Image.open(BytesIO(response.content)).convert("RGB")

    def get_current_art(self):
        """
        3 possible inputs (from self.art_url):
        url string   | Set wallpaper to this image (if it's not lastfm missing image)
        "default"    | Set default wallpaper
        None         | Do not change wallpaper

        4 Possible outputs
        Image.Image  | Generate and set wallpaper to this image
        "default"    | Set default wallpaper
        "generated"  | Set wallpaper to last generated wallpaper
        None         | Do not change wallpaper
        """
        image_url = self.art_url()
        if image_url == self.previous_image_url:  # Image hasn't changed
            return None

        self.previous_image_url = image_url

        if image_url in ("default", None):
            return image_url
        else:  # setting a new non-default wallpaper
            if (
                self.previously_generated_url == image_url
            ):  # wallpaper has already been generated
                return "generated"

            art = self.download_image(image_url)
            if ImageChops.difference(art, self.missing_art).getbbox() is None:
                return "default"
            else:
                self.previously_generated_url = image_url
                return art


class BatterySaverCheckThread(QtCore.QThread):
    # https://stackoverflow.com/a/33150936
    def __init__(self, pause_state_manager, parent=None):
        QtCore.QThread.__init__(self, parent)
        self.pause_state_manager = pause_state_manager

    def run(self):
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
        except Exception as e:
            app_log.exception("BatterySaverCheck Error")
            if __debug__:
                raise e


class WorkerThread(QtCore.QThread):
    def run(self):
        try:
            self.sleep = threading.Event()  # improves pause responsiveness

            self._pause_request = ConfigManager.settings["miscellaneous"]["paused"]
            self._battery_saver = (
                winapi.battery_saver_enabled()
                and not ConfigManager.settings["power"]["disable_on_battery_saver"]
            )

            self.disabled = False

            self.get_art = CurrentArt(service=ConfigManager.settings["service"]["name"])

            request_interval = ConfigManager.settings["service"]["request_interval"]

            wallaper_generator = GenerateWallpaper(app)

            while True:
                if self.disabled:
                    self.sleep.wait()

                image = self.get_art.get_current_art()
                wallaper_generator(image)
                self.sleep.wait(request_interval)

        except Exception as e:
            app_log.exception("Worker Error")
            if __debug__:
                raise e

    def check_state(self):
        if self.disabled:
            self.sleep.clear()
            Wallpaper.set(is_default=True)
        else:
            self.sleep.set()
            try:
                self.get_art.previous_image_url = None
            except AttributeError:
                pass

    @QtCore.Slot(str)
    def pause_state(self, state: str):
        if state in ("disabled", "battery_saver"):
            self.disabled = True
        else:
            self.disabled = False
        self.check_state()


class PauseStateSignals(QtCore.QObject):
    pause_state = QtCore.Signal(str)


class PauseStateManager:
    def __init__(self, signal):
        self.user_pause = ConfigManager.settings["miscellaneous"]["paused"]
        self.battery_saver = False

        mutex = QtCore.QMutex()
        self.locker = QtCore.QMutexLocker(mutex)
        self.signal = signal

    def toggle_pause(self):
        with self.locker:
            self.user_pause = not self.user_pause
            ConfigManager.settings["miscellaneous"]["paused"] = self.user_pause
            ConfigManager.save()
        self._send_signal()

    def set_battery_saver(self, enabled: bool):
        with self.locker:
            self.battery_saver = enabled
        self._send_signal()

    def _state(self) -> str:
        with self.locker:
            if self.battery_saver:
                return "battery_saver"
            elif self.user_pause:
                return "disabled"
            else:
                return "enabled"

    def _send_signal(self):
        self.signal.pause_state.emit(self._state())


"""
Some methods to run when the program starts
"""


class OnStartup:
    @staticmethod
    def start_logger():
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
            return app_log

        except Exception as e:
            if __debug__:
                raise e

    @staticmethod
    def start_QApplication():
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
        try:
            app = QtWidgets.QApplication(sys.argv)
        except RuntimeError:  # occurs on restart
            app = QtWidgets.QApplication.instance()

        app.setQuitOnLastWindowClosed(False)

        return app


"""
exit_code = 1, restart app
exit_code = 0, quit app
"""

if __name__ in "__main__":

    exit_code = 1

    while exit_code == 1:
        exit_code = 0
        app_log = OnStartup.start_logger()
        try:
            app = OnStartup.start_QApplication()

            widget = QtWidgets.QWidget()
            pause_state_signals = PauseStateSignals()

            pause_state_manager = PauseStateManager(pause_state_signals)

            tray_icon = SystemTrayIcon(
                icon=QtGui.QIcon("assets/icons/enabled.png"),
                parent=widget,
                signal=pause_state_signals,
                version=VERSION,
                pause_state_manager=pause_state_manager,
            )

            try:
                mutex = winapi.NamedMutex(b"AlbumPaper")
            except winapi.MutexNotAquiredError:
                tray_icon.showMessage("App already open", "")
                sys.exit()

            tray_icon.show()

            if not os.path.exists("images"):
                os.makedirs("images")
            if not os.path.exists("images/default_wallpaper.jpg"):
                Wallpaper.set_default()

            check_for_updates(tray_icon=tray_icon)

            try:
                ConfigManager.validate_service()
            except ConfigValidationError as e:
                tray_icon.showMessage(e.message, "")
                settings_window = SettingsWindow(tray_icon)
                exit_code = settings_window.exec_()
            else:
                battery_saver_check_thread = BatterySaverCheckThread(
                    pause_state_manager
                )
                battery_saver_check_thread.start(priority=QtCore.QThread.LowestPriority)

                worker_thread = WorkerThread()
                pause_state_signals.pause_state.connect(worker_thread.pause_state)

                pause_state_signals.pause_state.connect(tray_icon.pause_state)

                worker_thread.finished.connect(app.exit)
                worker_thread.start(priority=QtCore.QThread.LowPriority)

                pause_state_manager._send_signal()

                exit_code = app.exec_()

                worker_thread.terminate()

        except Exception as e:
            app_log.exception("main error")
            if __debug__:
                raise e

    mutex.release()
