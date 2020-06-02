import os, sys, time, json, glob, shutil, webbrowser, subprocess, ctypes, spotipy, urllib.request, configparser, requests, logging
import logging.handlers
from PySide2 import QtWidgets, QtGui, QtCore
from PIL import Image, ImageChops, ImageFilter
from colorthief import ColorThief
from themes import themes

version = "v1.3.1"  # As tagged on github

class TokenExpiredError(Exception):
    pass

class MissingArtError(Exception):
    pass

def spotify_auth():
    CLI_ID = config["Spotify"]["CLIENT_ID"]
    CLI_SEC = config["Spotify"]["CLIENT_SECRET"]

    REDIRECT_URI = "http://localhost:5000/callback/"
    SCOPE = "user-read-currently-playing"

    sp_oauth = spotipy.SpotifyOAuth(
        CLI_ID,
        CLI_SEC,
        redirect_uri = REDIRECT_URI,
        scope=SCOPE,
        cache_path=".cache",
        show_dialog=False
    )

    cached_token = sp_oauth.get_cached_token()

    if not cached_token:
        tray_icon.showMessage('Sign In','Please sign in')
        webbrowser.open("http://localhost:5000/")
        if os.path.exists('spotify-auth.py'):
            subprocess.run(["python", "spotify-auth.py"], shell=True, timeout=300)  # 5 minute timeout
        elif os.path.exists('spotify-auth.exe'):
            subprocess.run(["spotify-auth.exe"], shell=True, timeout=300)  # 5 minute timeout
        else:
            tray_icon.showMessage('Missing program','No spotify-auth program')
            sys.exit()
    
    if os.path.exists(".cache"):
        with open(".cache", "r") as f:
            data = json.load(f)
            token = data["access_token"]

        return spotipy.Spotify(auth=token)

    else:
        tray_icon.showMessage('Authorisation Error','Failed to sign in')
        sys.exit()


def spotify_current_track(sp):
    try:
        current = sp.currently_playing()
        return {
            "art_available":current["is_playing"],
            "image":current["item"]["album"]["images"][0]["url"],
        }
    except spotipy.client.SpotifyException:
        raise TokenExpiredError
    except:
        return {"art_available":False}


def lastfm_request(payload):
    try:
        # define headers and URL
        headers = {'user-agent': "album-art-wallpaper"}
        url = 'http://ws.audioscrobbler.com/2.0/'

        # Add API key and format to the payload
        payload['api_key'] = config["Last.fm"]["api_key"]
        payload['format'] = 'json'

        response = requests.get(url, headers=headers, params=payload)
        return response
    except:
        return None


def lastfm_current_track():
    try:
        current = lastfm_request({
            "method":"user.getRecentTracks",
            "limit":1,
            "user":config["Last.fm"]["username"]
        }).json()["recenttracks"]["track"][0]
    except KeyError: # Occurs when last.fm api fails or API keys are invalid
        return None
    except:
        # occurs with poor/no connection
        return {"art_available":False}
    try:
        return {
            "art_available":str_bool(current["@attr"]["nowplaying"]),
            "image": current["image"][0]["#text"].replace("34s","600x600"),
        }
    except: # occurs when the user isn't playing a track
        return {"art_available":False}


def str_bool(string):
    string = string.lower()
    if string == "false" or string == "0":
        return False
    elif string == "true" or string == "1":
        return True


def download_image(url):
    urllib.request.urlretrieve(url, "images/album-art.jpg")


def set_wallpaper(file_name):
    abs_path = os.path.abspath(file_name)
    ctypes.windll.user32.SystemParametersInfoW(20, 0, abs_path , 0)


def set_default_wallpaper():
    cached_folder = os.path.expandvars(r'%APPDATA%\Microsoft\Windows\Themes\CachedFiles\*')
    list_of_files = glob.glob(cached_folder)
    latest_file = max(list_of_files, key=os.path.getctime)
    shutil.copy(latest_file, "images/default_wallpaper.jpg")


def check_config(config):
    # invalid spotify keys
    if config["Service"]["service"].lower() == "spotify":
        if len(config["Spotify"]["CLIENT_SECRET"]) != 32 or \
            len(config["Spotify"]["CLIENT_ID"]) != 32:
            tray_icon.showMessage('Invalid API Keys','Set valid Spotify API Keys')
            return False

    # invalid last.fm key
    elif config["Service"]["service"].lower().replace(".","") == "lastfm":
        if len(config["Last.fm"]["api_key"]) != 32:
            tray_icon.showMessage('Invalid API Key','Set a valid Last.fm API key')
            return False

    # If a service isn't set
    else:
        tray_icon.showMessage('No sevice set','Set the service in settings to spotify or last.fm')
        return False

    return True  # valid config file

def check_file(path,end=True):
    if not os.path.exists(path):
        tray_icon.showMessage("Missing file",f"Can't find {path}")
        app_log.error(f"Missing file: {path}")
        if end:
            sys.exit()


class AlbumImage: # Make image manager?
    def __init__(self,image_path):
        self.image_path = image_path
        self.art = Image.open(image_path).convert('RGB')

        self.front_image_size = config["Settings"].getint("front_image_size")
        self.blur_image_size = config["Settings"].getint("blur_image_size")
        self.blur_radius = config["Settings"].getfloat("blur_image_radius")

        self.front_image_enabled = config["Settings"].getboolean("front_image_enabled")
        self.blur_image_enabled = config["Settings"].getboolean("blur_image_enabled")
        
        self.display_size = (ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1))

    def gen_color_layer(self):
        color_thief = ColorThief(self.image_path)
        color = color_thief.get_color(quality=50)
        return Image.new('RGB', self.display_size, color)

    def gen_blur_layer(self):
        if self.blur_image_enabled:
            art_resized = self.art.resize([self.blur_image_size]*2,1)
            return art_resized.filter(ImageFilter.GaussianBlur(self.blur_radius))
        else:
            return None

    def gen_front_layer(self):
        if self.front_image_enabled:
            return self.art.resize([self.front_image_size]*2,1)
        else:
            return None

    # ADD FUNCTIONALITY
    def is_missing_lastfm(self):
        if ImageChops.difference(self.art, Image.open("missing_art.jpg").convert('RGB')).getbbox() is None:
            return True
        else:
            return False

    def paste_images(self,base,*layers):
        for layer in layers:
            if layer is None:
                continue
            x = int((self.display_size[0] - layer.size[0])/2)
            y = int((self.display_size[1] - layer.size[1])/2)
            base.paste(layer,(x,y))
        base.save("images/generated_wallpaper.png")
        return None

    def generate_wallpaper(self):
        if not self.is_missing_lastfm():
            color_layer = self.gen_color_layer()
            blur_layer = self.gen_blur_layer()
            front_layer = self.gen_front_layer()
            self.paste_images(color_layer, blur_layer, front_layer)
            return None
        else:
            raise MissingArtError


class Worker(QtCore.QThread):
    # Worker thread
    @QtCore.Slot()
    def run(self):
        try:
            if config["Service"]["service"] == "spotify":
                using_spotify = True
                sp = spotify_auth()
            else:
                using_spotify = False

            previous_wallpaper = None
            request_interval = config["Settings"].getfloat("request_interval")

            while True:
                time.sleep(request_interval)
                if using_spotify:
                    try:
                        current = spotify_current_track(sp)
                    except TokenExpiredError:
                        sp = spotify_auth()
                        continue
                else:
                    current = lastfm_current_track()
                    if current is None:
                        continue
                if current["art_available"]:
                    if current["image"] != previous_wallpaper:
                        download_image(current["image"])
                        # try:  # Error raised when a user skips tracks rapidly after a restart
                        image = AlbumImage("images/album-art.jpg")
                        image.generate_wallpaper()
                        set_wallpaper("images/generated_wallpaper.png")
                        previous_wallpaper = current["image"]
                        # except:
                        #     previous_wallpaper = None
                elif previous_wallpaper is not None:
                    set_wallpaper("images/default_wallpaper.jpg")
                    previous_wallpaper = None

        except:
            app_log.exception("worker error")



class SettingsWindow(QtWidgets.QDialog):
    def __init__(self,parent=None):
        if config["Service"]["service"].lower() == "spotify":
            using_spotify = True
        else:
            using_spotify = False

        super(SettingsWindow,self).__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedSize(540, 0)
        if os.path.exists("settings_icon.png"):
            self.setWindowIcon(QtGui.QIcon("settings_icon.png"))

        # spotify section
        self.spotify_radio_button = QtWidgets.QRadioButton("Spotify",checkable=True)
        self.spotify_radio_button.setChecked(using_spotify)

        self.spotify_client_id = QtWidgets.QLineEdit()
        self.spotify_client_secret = QtWidgets.QLineEdit()
        self.spotify_client_id.setPlaceholderText("Client ID")
        self.spotify_client_secret.setPlaceholderText("Client Secret")
        self.spotify_client_id.setMaxLength(32)
        self.spotify_client_secret.setMaxLength(32)
        self.spotify_client_id.setText(config["Spotify"]["CLIENT_ID"])
        self.spotify_client_secret.setText(config["Spotify"]["CLIENT_SECRET"])

        # last.fm section
        self.lastfm_radio_button = QtWidgets.QRadioButton("Last.fm",checkable=True)
        self.lastfm_radio_button.setChecked(not using_spotify)

        self.lastfm_username = QtWidgets.QLineEdit()
        self.lastfm_api_key = QtWidgets.QLineEdit()
        self.lastfm_username.setPlaceholderText("Username")
        self.lastfm_api_key.setPlaceholderText("API Key")
        self.lastfm_api_key.setMaxLength(32)
        self.lastfm_username.setText(config["Last.fm"]["username"])
        self.lastfm_api_key.setText(config["Last.fm"]["api_key"])

        # other settings
        self.request_interval = QtWidgets.QDoubleSpinBox()
        self.request_interval.setRange(0.0,60.0)
        self.request_interval.setSingleStep(0.5)
        self.request_interval.setValue(config["Settings"].getfloat("request_interval"))
        
        self.art_size = QtWidgets.QSpinBox()
        self.art_size.setRange(1,10_000)
        self.art_size.setValue(config["Settings"].getint("front_image_size"))
        
        self.save_button = QtWidgets.QPushButton("Save")
        self.save_button.clicked.connect(self.save)

        # radio buttons
        self.radio_buttons = QtWidgets.QButtonGroup()
        self.radio_buttons.addButton(self.spotify_radio_button)
        self.radio_buttons.addButton(self.lastfm_radio_button)


        layout = QtWidgets.QFormLayout()
        # Spotify section
        spotify_help_link = QtWidgets.QLabel(f'<a href="https://github.com/jac0b-w/album-art-wallpaper/blob/{version}/README.md#spotify">Where do I find these?</a>')
        spotify_help_link.linkActivated.connect(self.open_link)
        layout.addRow(spotify_help_link,self.spotify_radio_button)
        layout.addRow("Client ID:",self.spotify_client_id)
        layout.addRow("Client Secret:",self.spotify_client_secret)
        # Last.fm section
        lastfm_help_link = QtWidgets.QLabel(f'<a href="https://github.com/jac0b-w/album-art-wallpaper/blob/{version}/README.md#lastfm">Where do I find these?</a>')
        lastfm_help_link.linkActivated.connect(self.open_link)
        layout.addRow(lastfm_help_link,self.lastfm_radio_button)
        layout.addRow("Username:",self.lastfm_username)
        layout.addRow("API Key:",self.lastfm_api_key)

        layout.addRow(QtWidgets.QLabel(""))
        layout.addRow("Request Interval (s):",self.request_interval)
        layout.addRow("Art size (px):",self.art_size)
        layout.addRow("Restart required",self.save_button)

        # styling
        try:
            self.setStyleSheet(themes[config["Settings"]["theme"]]["settings_window"])
        except KeyError:
            pass

        self.setLayout(layout)
        
        self.exec_()

    def save(self):
        if self.spotify_radio_button.isChecked():
            config["Service"]["service"] = "spotify"
        else:
            config["Service"]["service"] = "last.fm"

        config["Spotify"]["CLIENT_ID"] = self.spotify_client_id.text()
        config["Spotify"]["CLIENT_SECRET"] = self.spotify_client_secret.text()

        config["Last.fm"]["api_key"] = self.lastfm_api_key.text()
        config["Last.fm"]["username"] = self.lastfm_username.text()

        config["Settings"]["request_interval"] = self.request_interval.value()
        config["Settings"]["front_image_size"] = self.art_size.value()

        if check_config(config):
            with open("config.ini","w") as f:
                config.write(f)

            self.close()

    def open_link(self,link):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(link))

class SystemTrayIcon(QtWidgets.QSystemTrayIcon):
    def __init__(self, icon, parent=None):
        QtWidgets.QSystemTrayIcon.__init__(self, icon, parent)
        self.setToolTip('Album Art Wallpaper')
        self.menu = QtWidgets.QMenu(parent)
        self.cursor = QtGui.QCursor()

        try:
            self.menu.setStyleSheet(themes[config["Settings"]["theme"]]["menu"])
        except KeyError:
            pass

        default_wallpaper_item = self.menu.addAction("Set Default Wallpaper")
        default_wallpaper_item.triggered.connect(self.set_default_wallpaper)

        self.menu.addSeparator()

        settings_item = self.menu.addAction("Settings")
        settings_item.triggered.connect(self.settings)

        self.menu.addSeparator()

        self.help_menu = self.menu.addMenu("Help")
        help_latest = self.help_menu.addAction("Lastest Release")
        help_current = self.help_menu.addAction("This Release")
        help_latest.triggered.connect(self.open_link("https://github.com/jac0b-w/album-art-wallpaper/blob/master/README.md"))
        help_current.triggered.connect(self.open_link(f"https://github.com/jac0b-w/album-art-wallpaper/blob/{version}/README.md"))

        bug_report_item = self.menu.addAction("Bug Report")
        bug_report_item.triggered.connect(self.open_link("https://github.com/jac0b-w/album-art-wallpaper/issues"))

        release_item = self.menu.addAction(f"{version}")
        release_item.triggered.connect(self.open_link("https://github.com/jac0b-w/album-art-wallpaper/releases"))

        self.menu.addSeparator()

        restart_item = self.menu.addAction("Restart")
        restart_item.triggered.connect(self.exit(1))

        exit_item = self.menu.addAction("Quit")
        exit_item.triggered.connect(self.exit(0))

        self.setContextMenu(self.menu)
        self.activated.connect(self.onTrayIconActivated)
    
    def onTrayIconActivated(self, reason):
        if reason == self.Trigger:  # self.Trigger is left click
            self.menu.setGeometry(*self.context_menu_pos())
            self.menu.show()

    def context_menu_pos(self):
        menu_width = 170
        menu_height = 187
        screen_width = ctypes.windll.user32.GetSystemMetrics(0)
        screen_height = ctypes.windll.user32.GetSystemMetrics(1)

        if self.cursor.pos().x() + menu_width > screen_width:
            x = screen_width - menu_width
        else:
            x = self.cursor.pos().x()

        if self.cursor.pos().y() + menu_height > screen_height:
            y = self.cursor.pos().y() - menu_height
        else:
            y = self.cursor.pos().y()

        return x,y,menu_width,menu_height

    def settings(self):
        settings_window = SettingsWindow()
        settings_window.show()

    def set_default_wallpaper(self):
        set_default_wallpaper()
        self.showMessage('Saved','Wallpaper saved as default')

    def open_link(self,link):
        return lambda: webbrowser.open(link)

    def exit(self,exit_code):
        def exit_function():
            set_wallpaper("images/default_wallpaper.jpg")
            return QtWidgets.QApplication.exit(exit_code)
        
        return exit_function

'''
exit_code = 1, restart app
exit_code = 0, quit app
'''

if __name__ in "__main__":
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

    while exit_code != 0:
        try:
            config = configparser.ConfigParser()
            config.read('config.ini')

            try:
                app = QtWidgets.QApplication(sys.argv)
            except RuntimeError:
                app = QtWidgets.QApplication.instance()

            w = QtWidgets.QWidget()
            tray_icon = SystemTrayIcon(QtGui.QIcon("icon.ico"), w)
            tray_icon.show()

            if not os.path.exists('images'):
                os.makedirs('images')
            if not os.path.exists("images/default_wallpaper.jpg"):
                set_default_wallpaper()

            check_file("config.ini",True)
            check_file("icon.ico",True)
            check_file("missing_art.jpg",True)
            check_file("settings_icon.png",False)

            if check_config(config):
                thread = Worker()
                thread.finished.connect(app.exit)
                thread.start()

                exit_code = app.exec_()

            else:
                settings_window = SettingsWindow()
                settings_window.show()

        except:
            app_log.exception("main error")
            exit_code = 0
