# external imports
import os, sys, spotipy, requests, logging, logging.handlers, threading
from PySide2 import QtWidgets, QtGui, QtCore
from PIL import Image, ImageChops
from io import BytesIO

# In this directory
from ui import SystemTrayIcon, SettingsWindow
from config import config  # object
from wallpaper import Wallpaper, GenerateWallpaper
from mutex import MutexNotAquiredError, NamedMutex

def spotify_auth():
    client_id = config.spotify["client_id"]
    client_secret = config.spotify["client_secret"]

    redirect_uri = "http://localhost:8080/"
    scope = "user-read-currently-playing"

    sp_oauth = spotipy.SpotifyOAuth(
        client_id,
        client_secret,
        redirect_uri = redirect_uri,
        scope=scope,
        cache_path=".cache",
        show_dialog=True
    )

    token_info = sp_oauth.get_access_token(as_dict=True)
    token = token_info["access_token"]

    try:
        return spotipy.Spotify(auth=token),sp_oauth,token_info
    except Exception:
        print("User token could not be created")
        sys.exit()

def check_file(*paths, quit_if_missing=True):
    for path in paths:
        if not os.path.exists(path):
            tray_icon.showMessage("Missing file",f"Can't find {path}")
            app_log.error(f"Missing file: {path}")
            if quit_if_missing:
                sys.exit()

class CurrentArt():
    def __init__(self, sp=None):
        if sp is None:  # using lastfm
            self.art_url = self.lastfm_art_url
        else:
            self.art_url = self.spotify_art_url
            self.sp, self.sp_oauth, self.token_info = spotify_auth()
        
        self.missing_art = Image.open("assets/missing_art.jpg").convert('RGB')
        self.previous_image_url = None
        self.previously_generated_url = None
    
    def spotify_art_url(self) -> str:
        try:
            self.refresh_token()
            current = self.sp.currently_playing()
            if current["is_playing"]:
                return current["item"]["album"]["images"][0]["url"]
            else:
                return "default"
        except spotipy.client.SpotifyException: # Token expired
            self.refresh_token()
        except:  # local tracks, no devices playing
            return "default"

    def refresh_token(self):
        try:
            if self.sp_oauth.is_token_expired(token_info=self.token_info):
                self.token_info = self.sp_oauth.refresh_access_token(self.token_info['refresh_token'])
                token = self.token_info['access_token']
                self.sp = spotipy.Spotify(auth=token)
                print("TOKEN REFRESHED")
        except:
            print("FAILED TO REFRESH TOKEN")

    def lastfm_request(self):
        try:
            # define headers and URL
            headers = {'user-agent': "AlbumPaper"}
            url = 'http://ws.audioscrobbler.com/2.0/'

            payload = {
                "method":"user.getRecentTracks",
                "limit":1,
                "user":config.lastfm["username"],
                "api_key":config.lastfm["api_key"],
                "format":"json"
            }

            response = requests.get(url, headers=headers, params=payload)
            return response
        except:
            print("[ERROR] Last.fm request error")
            return None

    def lastfm_art_url(self):
        try:
            current = self.lastfm_request().json()["recenttracks"]["track"][0]
        except KeyError: # Occurs when last.fm api fails (briefly) or API keys are invalid
            return None
        except:
            # occurs with poor/no connection
            return "default"
        try:
            if current["@attr"]["nowplaying"].lower() == "true":
                return current["image"][0]["#text"].replace("34s","600x600")
            else:   # when track is not playing
                return "default"
        except: # occurs when the user isn't playing a track
            return "default"

    @staticmethod
    def download_image(url: str) -> Image.Image:
        print("IMAGE DOWNLOADED")
        response = requests.get(url)
        return Image.open(BytesIO(response.content)).convert("RGB")

    def get_current_art(self):
        '''
        3 possible inputs (from self.art_url):
        url string   | Set wallpaper to this image (if it's not lastfm missing image)
        "default"    | Set default wallpaper
        None         | Do not change wallpaper

        4 Possible outputs
        Image.Image  | Generate and set wallpaper to this image
        "default"    | Set default wallpaper
        "generated"  | Set wallpaper to last generated wallpaper
        None         | Do not change wallpaper
        '''
        image_url = self.art_url()
        if (image_url == self.previous_image_url):  # Image hasn't changed
            return None

        self.previous_image_url = image_url

        if image_url in ("default",None):
            return image_url
        else:   # setting a new non-default wallpaper
            if (self.previously_generated_url == image_url):  # wallpaper has already been generated
                return "generated"
            
            art = self.download_image(image_url)
            if ImageChops.difference(art, self.missing_art).getbbox() is None:
                return "default"
            else:
                self.previously_generated_url = image_url
                return art


class WorkerSignals(QtCore.QObject):
    pause_state = QtCore.Signal(bool)


class Worker(QtCore.QThread):
    # Worker thread
    @QtCore.Slot()
    def run(self):
        try:
            self.sleep = threading.Event()  # improves pause responsiveness
            self.is_paused = False

            if config.settings["service"] == "spotify":
                sp, *__ = spotify_auth()
                get_art = CurrentArt(sp)
            else:
                get_art = CurrentArt()

            request_interval = config.settings.getfloat("request_interval")

            generate_wallpaper = GenerateWallpaper(app)

            while True:
                image = get_art.get_current_art()
                generate_wallpaper(image)

                if self.is_paused:
                    self.sleep.wait()
                    get_art.previous_image_url = None
                else:
                    self.sleep.wait(request_interval)

        except Exception as e:
            app_log.exception("worker error")
            if __debug__:
                raise(e)

    @QtCore.Slot(bool)
    def pause_state(self, is_paused: bool):
        self.is_paused = is_paused
        if is_paused:
            self.sleep.clear()
            Wallpaper.set(is_default=True)
        else:
            self.sleep.set()

'''
exit_code = 1, restart app
exit_code = 0, quit app
'''

if __name__ in "__main__":
    try:
        exit_code = 1

        # logging errors
        handler = logging.handlers.RotatingFileHandler(
            "errors.log",
            maxBytes=500*1024,  # 500 kB
            backupCount=1,
        )
        handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
        handler.setLevel(logging.ERROR)
        app_log = logging.getLogger("root")
        app_log.setLevel(logging.ERROR)
        app_log.addHandler(handler)
    except Exception as e:
        app_log.exception("Startup error")
        if __debug__:
            raise(e)

    while exit_code == 1:
        exit_code = 0
        try:
            try:
                app = QtWidgets.QApplication(sys.argv)
            except RuntimeError: # occurs on restart
                app = QtWidgets.QApplication.instance()

            app.setQuitOnLastWindowClosed(False)
            widget = QtWidgets.QWidget()
            signal = WorkerSignals()

            tray_icon = SystemTrayIcon(
                icon = QtGui.QIcon("assets/enabled.png"),
                parent = widget,
                signal = signal
            )

            try:
                mutex = NamedMutex(b"AlbumPaper")
            except MutexNotAquiredError:
                tray_icon.showMessage("App already open", "")
                sys.exit()

            tray_icon.show()

            if not os.path.exists('images'):
                os.makedirs('images')
            if not os.path.exists("images/default_wallpaper.jpg"):
                Wallpaper.set_default()

            check_file(
                "settings.ini",
                "services.ini",
                "assets/enabled.png",
                "assets/disabled.png",
                "assets/missing_art.jpg",
                quit_if_missing = True)
            check_file(
                "assets/settings_icon.png",
                quit_if_missing = False)

            if config.check_valid(tray_icon):
                thread = Worker()
                signal.pause_state.connect(thread.pause_state)
                thread.finished.connect(app.exit)
                thread.start()

                exit_code = app.exec_()

                thread.terminate()
            else:
                settings_window = SettingsWindow(tray_icon)
                exit_code = settings_window.exec_()

        except Exception as e:
            app_log.exception("main error")
            if __debug__:
                raise(e)

    mutex.release()
