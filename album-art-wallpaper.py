import os, sys, time, json, glob, shutil, ctypes, spotipy, configparser, requests, logging, numpy, themes, webbrowser
import logging.handlers, scipy.cluster
from PySide2 import QtWidgets, QtGui, QtCore
from PIL import Image, ImageChops, ImageFilter
from io import BytesIO


__version__ = "v2.0.2"  # As tagged on github


def spotify_auth():
    CLI_ID = config["Spotify"]["CLIENT_ID"]
    CLI_SEC = config["Spotify"]["CLIENT_SECRET"]

    REDIRECT_URI = "http://localhost:8080/"
    SCOPE = "user-read-currently-playing"

    sp_oauth = spotipy.SpotifyOAuth(
        CLI_ID,
        CLI_SEC,
        redirect_uri = REDIRECT_URI,
        scope=SCOPE,
        cache_path=".cache",
        show_dialog=True
    )

    token_info = sp_oauth.get_access_token(as_dict=True)
    token = token_info["access_token"]

    try:
        return spotipy.Spotify(auth=token),sp_oauth,token_info
    except:
        print("User token could not be created")
        sys.exit()
    

def set_wallpaper(is_default):
    if is_default:
        file_name = "images/default_wallpaper.jpg"
    else:
        file_name = "images/generated_wallpaper.jpg"
    abs_path = os.path.abspath(file_name)
    ctypes.windll.user32.SystemParametersInfoW(20, 0, abs_path , 0)
    print("SET NEW WALLPAPER")


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
            print("INVALID SPOTIFY KEY")
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

def check_file(path,quit_if_missing=True):
    if not os.path.exists(path):
        tray_icon.showMessage("Missing file",f"Can't find {path}")
        app_log.error(f"Missing file: {path}")
        if quit_if_missing:
            sys.exit()


class Timer:
    def __init__(self):
        self.time = time.time()

    def ping(self,name):
        print(f"{name} took {time.time()-self.time}")
        self.time = time.time()


class CurrentArt():
    def __init__(self,sp=None):
        if sp is None:  # using lastfm
            self.art_url = self.lastfm_art_url
        else:
            self.art_url = self.spotify_art_url
            self.sp,self.sp_oauth,self.token_info = sp,sp_oauth,token_info = spotify_auth()
        
        self.missing_art = Image.open("assets/missing_art.jpg").convert('RGB')
        self.previous_image_url = None
        self.previously_generated_url = None
    
    def spotify_art_url(self):
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

    def str_bool(self,string):
        return string.lower() == "true"

    def lastfm_request(payload):
        try:
            # define headers and URL
            headers = {'user-agent': "album-art-wallpaper"}
            url = 'http://ws.audioscrobbler.com/2.0/'

            payload = {
                "method":"user.getRecentTracks",
                "limit":1,
                "user":config["Last.fm"]["username"],
                "api_key":config["Last.fm"]["api_key"],
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
        except KeyError: # Occurs when last.fm api fails (breifly) or API keys are invalid
            return None
        except:
            # occurs with poor/no connection
            return "default"
        try:
            if self.str_bool(current["@attr"]["nowplaying"]):
                return current["image"][0]["#text"].replace("34s","600x600")
            else:   # when track is not playing
                return "default"
        except: # occurs when the user isn't playing a track
            return "default"

    def download_image(self,url):
        print("IMAGE DOWNLOADED")
        response = requests.get(url)
        return Image.open(BytesIO(response.content)).convert("RGB")

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
    
    def get_current_art(self):
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


class GenerateWallpaper:
    def __init__(self):
        self.front_image_size = config["Settings"].getint("front_image_size")
        self.blur_image_size = config["Settings"].getint("blur_image_size")
        self.blur_radius = config["Settings"].getfloat("blur_image_radius")

        self.front_image_enabled = config["Settings"].getboolean("front_image_enabled")
        self.blur_image_enabled = config["Settings"].getboolean("blur_image_enabled")
        
        dw = app.desktop()  # dw = QDesktopWidget() also works if app is created
        self.display_size = (dw.screenGeometry().width(),dw.screenGeometry().height())
        self.avaliable_size = (dw.availableGeometry().width(),dw.availableGeometry().height())

    def dominant_color(self,image):
        NUM_CLUSTERS = 5

        image = image.resize((150, 150))      # optional, to reduce time
        ar = numpy.asarray(image)
        shape = ar.shape
        ar = ar.reshape(numpy.product(shape[:2]), shape[2]).astype(float)

        codes, dist = scipy.cluster.vq.kmeans(ar, NUM_CLUSTERS)

        vecs, dist = scipy.cluster.vq.vq(ar, codes)         # assign codes
        counts, bins = numpy.histogram(vecs, len(codes))    # count occurrences

        index_max = numpy.argmax(counts)                    # find most frequent
        color = tuple([int(code) for code in codes[index_max]])
        return color

    def gen_color_layer(self,image):
        color = self.dominant_color(image)
        return Image.new("RGB",self.display_size,color)

    def gen_blur_layer(self,image):
        if self.blur_image_enabled:
            art_resized = image.resize([self.blur_image_size]*2,1)
            return art_resized.filter(ImageFilter.GaussianBlur(self.blur_radius))
        else:
            return None

    def gen_front_layer(self,image):
        if self.front_image_enabled:
            return image.resize([self.front_image_size]*2,1)
        else:
            return None

    def save_image(self,path,image):
        try:
            image.save(path,"JPEG",quality=95)
        except OSError:
            time.sleep(0.1)
            self.save_image(path,image)

    def paste_images(self,base,*layers):
        for layer in layers:
            if layer is None:
                continue
            x = int((self.avaliable_size[0] - layer.size[0])/2)
            y = int((self.avaliable_size[1] - layer.size[1])/2)
            base.paste(layer,(x,y))
        self.save_image("images/generated_wallpaper.jpg",base)

    def generate_wallpaper(self,image):
        if isinstance(image,Image.Image):
            timer = Timer()
            color_layer = self.gen_color_layer(image)
            timer.ping("color layer")
            blur_layer = self.gen_blur_layer(image)
            timer.ping("blur layer")
            front_layer = self.gen_front_layer(image)
            timer.ping("front layer")
            self.paste_images(color_layer, blur_layer, front_layer)
            timer.ping("paste images")
            set_wallpaper(False)
        elif image == "default":
            set_wallpaper(True)
        elif image == "generated":
            set_wallpaper(False)


class Worker(QtCore.QThread):
    # Worker thread
    @QtCore.Slot()
    def run(self):
        try:
            if config["Service"]["service"] == "spotify":
                sp,sp_oauth,token_info = spotify_auth()
                get_art = CurrentArt(sp)
            else:
                get_art = CurrentArt()

            previous_wallpaper = None
            request_interval = config["Settings"].getfloat("request_interval")

            set_wallpaper = GenerateWallpaper()


            while True:
                time.sleep(request_interval)

                image = get_art.get_current_art()
                set_wallpaper.generate_wallpaper(image)

        except:
            app_log.exception("worker error")


class SettingsWindow(QtWidgets.QDialog):
    def __init__(self,parent=None):
        using_spotify = (config["Service"]["service"].lower() == "spotify")

        super(SettingsWindow,self).__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedSize(540, 0)
        if os.path.exists("assets/settings_icon.png"):
            self.setWindowIcon(QtGui.QIcon("assets/settings_icon.png"))
        # self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        # spotify section
        self.spotify_radio_button = QtWidgets.QRadioButton(checkable=True)
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
        self.lastfm_radio_button = QtWidgets.QRadioButton(checkable=True)
        self.lastfm_radio_button.setChecked(not using_spotify)

        self.lastfm_username = QtWidgets.QLineEdit()
        self.lastfm_api_key = QtWidgets.QLineEdit()
        self.lastfm_username.setPlaceholderText("Username")
        self.lastfm_api_key.setPlaceholderText("API Key")
        self.lastfm_api_key.setMaxLength(32)
        self.lastfm_username.setText(config["Last.fm"]["username"])
        self.lastfm_api_key.setText(config["Last.fm"]["api_key"])

        # radio buttons group
        self.radio_buttons = QtWidgets.QButtonGroup()
        self.radio_buttons.addButton(self.spotify_radio_button)
        self.radio_buttons.addButton(self.lastfm_radio_button)

        # layer settings
        self.front_image_checkbox = QtWidgets.QCheckBox()
        self.front_image_checkbox.setChecked(config["Settings"].getboolean("front_image_enabled"))
        self.front_image_size = QtWidgets.QSpinBox()
        self.front_image_size.setRange(1,10_000)
        self.front_image_size.setValue(config["Settings"].getint("front_image_size"))

        self.blur_image_checkbox = QtWidgets.QCheckBox()
        self.blur_image_checkbox.setChecked(config["Settings"].getboolean("blur_image_enabled"))
        self.blur_image_size = QtWidgets.QSpinBox()
        self.blur_image_size.setRange(1,10_000)
        self.blur_image_size.setValue(config["Settings"].getint("blur_image_size"))
        self.blur_image_radius = QtWidgets.QDoubleSpinBox()
        self.blur_image_radius.setRange(0.0,100.0)
        self.blur_image_radius.setSingleStep(0.5)
        self.blur_image_radius.setValue(config["Settings"].getfloat("blur_image_radius"))

        # other settings
        self.theme_selector = QtWidgets.QComboBox()
        for theme in themes.themes:
            self.theme_selector.addItem(theme)
        self.theme_selector.setCurrentIndex(
            self.theme_selector.findText(config["Settings"]["theme"],
            QtCore.Qt.MatchFixedString)
        )

        self.request_interval = QtWidgets.QDoubleSpinBox()
        self.request_interval.setRange(0.0,60.0)
        self.request_interval.setSingleStep(0.5)
        self.request_interval.setValue(config["Settings"].getfloat("request_interval"))
        
        self.save_button = QtWidgets.QPushButton("Save")
        self.save_button.clicked.connect(self.save)
        
        # layout
        layout = QtWidgets.QFormLayout()

        help_link = QtWidgets.QLabel(f'<a href="https://github.com/jac0b-w/album-art-wallpaper#getting-started">Where do I find these?</a>')
        help_link.linkActivated.connect(self.open_link)
        layout.addRow(help_link)

        # Spotify section
        layout.addRow("Spotify (recommended)",self.spotify_radio_button)
        layout.addRow("Client ID",self.spotify_client_id)
        layout.addRow("Client Secret",self.spotify_client_secret)

        layout.addRow(QtWidgets.QLabel(""))
        # Last.fm section
        layout.addRow("Last.fm",self.lastfm_radio_button)
        layout.addRow("Username",self.lastfm_username)
        layout.addRow("API Key",self.lastfm_api_key)

        layout.addRow(QtWidgets.QLabel(""))
        # layer settings
        layout.addRow("Art Image",self.front_image_checkbox)
        layout.addRow("Art Image Size (px)",self.front_image_size)
        layout.addRow("Blur Image",self.blur_image_checkbox)
        layout.addRow("Blur Image Size (px)",self.blur_image_size)
        layout.addRow("Blur Strength",self.blur_image_radius)

        layout.addRow(QtWidgets.QLabel(""))

        # other settings
        layout.addRow("Theme",self.theme_selector)
        layout.addRow("Request Interval (s)",self.request_interval)
        layout.addRow("",self.save_button)

        # styling
        self.setStyleSheet(themes.themes[config["Settings"]["theme"]]["settings_window"])

        self.setLayout(layout)

    def save(self):
        if self.spotify_radio_button.isChecked():
            config["Service"]["service"] = "spotify"
        else:
            config["Service"]["service"] = "last.fm"

        config["Spotify"]["CLIENT_ID"] = self.spotify_client_id.text()
        config["Spotify"]["CLIENT_SECRET"] = self.spotify_client_secret.text()

        config["Last.fm"]["api_key"] = self.lastfm_api_key.text()
        config["Last.fm"]["username"] = self.lastfm_username.text()

        # layer settings
        config["Settings"]["front_image_enabled"] = str(self.front_image_checkbox.isChecked())
        config["Settings"]["front_image_size"] = str(self.front_image_size.value())
        config["Settings"]["blur_image_enabled"] = str(self.blur_image_checkbox.isChecked())
        config["Settings"]["blur_image_size"] = str(self.blur_image_size.value())
        config["Settings"]["blur_image_radius"] = str(self.blur_image_radius.value())

        config["Settings"]["theme"] = self.theme_selector.currentText()
        config["Settings"]["request_interval"] = str(self.request_interval.value())

        if check_config(config):
            with open("config.ini","w") as f:
                config.write(f)

            QtWidgets.QApplication.exit(1)

    def open_link(self,link):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(link))

    

class SystemTrayIcon(QtWidgets.QSystemTrayIcon):
    def __init__(self, icon, parent=None):
        QtWidgets.QSystemTrayIcon.__init__(self, icon, parent)
        self.setToolTip('Album Art Wallpaper')
        self.menu = QtWidgets.QMenu(parent)
        self.cursor = QtGui.QCursor()

        try:
            self.menu.setStyleSheet(themes.themes[config["Settings"]["theme"]]["menu"])
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
        help_current.triggered.connect(self.open_link(f"https://github.com/jac0b-w/album-art-wallpaper/blob/{__version__}/README.md"))

        bug_report_item = self.menu.addAction("Bug Report")
        bug_report_item.triggered.connect(self.open_link("https://github.com/jac0b-w/album-art-wallpaper/issues"))

        release_item = self.menu.addAction(f"{__version__}")
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
        settings_window.show()
        settings_window.activateWindow()

    def set_default_wallpaper(self):
        set_default_wallpaper()
        self.showMessage('Saved','Wallpaper saved as default')

    def open_link(self,link):
        return lambda: webbrowser.open(link)

    def exit(self,exit_code):
        def exit_function():
            set_wallpaper(is_default = True)
            QtWidgets.QApplication.exit(exit_code)
        
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

    while exit_code == 1:
        exit_code = 0
        try:
            config = configparser.ConfigParser()
            config.read('config.ini')

            try:
                app = QtWidgets.QApplication(sys.argv)
            except RuntimeError:
                app = QtWidgets.QApplication.instance()

            app.setQuitOnLastWindowClosed(False)
            w = QtWidgets.QWidget()
            tray_icon = SystemTrayIcon(QtGui.QIcon("assets/icon.ico"), w)
            tray_icon.show()
            settings_window = SettingsWindow()

            if not os.path.exists('images'):
                os.makedirs('images')
            if not os.path.exists("images/default_wallpaper.jpg"):
                set_default_wallpaper()

            check_file("config.ini",True)
            check_file("assets/icon.ico",True)
            check_file("assets/missing_art.jpg",True)
            check_file("assets/settings_icon.png",False)

            if check_config(config):
                thread = Worker()
                thread.finished.connect(app.exit)
                thread.start()

                exit_code = app.exec_()
                thread.terminate()

            else:
                settings_window.exec_()

        except:
            app_log.exception("main error")
