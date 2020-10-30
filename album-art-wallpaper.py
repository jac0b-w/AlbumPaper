import os, sys, time, json, glob, shutil, ctypes, spotipy, configparser
import requests, logging, numpy, ast, collections
import logging.handlers, scipy.cluster, sklearn.cluster
from PySide2 import QtWidgets, QtGui, QtCore
from PIL import Image, ImageChops, ImageFilter, ImageDraw
from io import BytesIO


__version__ = "v3.1"  # As tagged on github


def timer(func):
    def wrapper(*args,**kwargs):
        start = time.time()
        return_values = func(*args,**kwargs)
        if time.time() - start > 0.005:
            print(f"function {func.__name__} took {time.time() - start} seconds")
        return return_values
    return wrapper


def spotify_auth():
    CLI_ID = config["Spotify"]["client_id"]
    CLI_SEC = config["Spotify"]["client_secret"]

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
    except Exception:
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
    """
    1. First look in %APPDATA%\Microsoft\Windows\Themes\CachedFiles
    and use most recent image
    2. If that fails look for %APPDATA%\Microsoft\Windows\Themes\TranscodedWallpaper
    3. If that fails find the original path of the wallpaper and save that image instead
    # https://stackoverflow.com/questions/44867820/
    4. Finally if all fail just save use a blank image as the dafault wallpaper
    """
    default_wallpaper_path = "images/default_wallpaper.jpg"
    cached_folder = os.path.expandvars(r'%APPDATA%\Microsoft\Windows\Themes\CachedFiles\*')
    list_of_files = glob.glob(cached_folder)
    if list_of_files:
        current_wallpaper = max(list_of_files, key=os.path.getctime)
    else:
        current_wallpaper = os.path.expandvars(
        r'%APPDATA%\Microsoft\Windows\Themes\TranscodedWallpaper')
    try:
        shutil.copy(current_wallpaper, default_wallpaper_path)
    except FileNotFoundError:
        ubuf = ctypes.create_unicode_buffer(200)
        ctypes.windll.user32.SystemParametersInfoW(0x0073,200,ubuf,0)
        try:
            shutil.copy(ubuf.value, default_wallpaper_path)
        except FileNotFoundError:
            image = Image.new("RGB",(1,1))
            image.save(default_wallpaper_path,"JPEG",quality=95)

def check_config(config):
    # invalid spotify keys
    if config["Service"]["service"].lower() == "spotify":
        if len(config["Spotify"]["client_secret"]) != 32 or \
            len(config["Spotify"]["client_id"]) != 32:
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


def check_file(*paths,quit_if_missing=True):
    for path in paths:
        if not os.path.exists(path):
            tray_icon.showMessage("Missing file",f"Can't find {path}")
            app_log.error(f"Missing file: {path}")
            if quit_if_missing:
                sys.exit()


class ConfigManager:
    def __init__(self):
        self.services = configparser.ConfigParser()
        self.services.read('services.ini')
        self.settings = configparser.ConfigParser()
        self.settings.read('settings.ini')

    def __getitem__(self,key):
        if key in ("Service","Spotify","Last.fm"):
            return self.services[key]
        else:
            return self.settings[key]

    def save(self):
        with open("settings.ini","w") as f:
            self.settings.write(f)
        with open("services.ini","w") as f:
            self.services.write(f)


class CurrentArt():
    def __init__(self,sp=None):
        if sp is None:  # using lastfm
            self.art_url = self.lastfm_art_url
        else:
            self.art_url = self.spotify_art_url
            self.sp, self.sp_oauth, self.token_info = spotify_auth()
        
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

    def lastfm_request(self):
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
            if current["@attr"]["nowplaying"].lower() == "true":
                return current["image"][0]["#text"].replace("34s","600x600")
            else:   # when track is not playing
                return "default"
        except: # occurs when the user isn't playing a track
            return "default"

    @staticmethod
    def download_image(url):
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


class GenerateWallpaper:
    def __init__(self):
        self.foreground_size = config["Settings"].getint("foreground_size")
        background_type = config["Settings"].get("background_type")
        self.gen_background = {
            "Solid":self.color_background,
            "Gradient":self.gradient_background,
            "Art":self.art_background,
            "Wallpaper":self.wallpaper_background
        }[background_type]

        self.blur_enabled = config["Settings"].getboolean("blur_enabled")
        self.blur_strength = config["Settings"].getfloat("blur_strength")

        self.foreground_enabled = config["Settings"].getboolean("foreground_enabled")
        
        Geometry = collections.namedtuple('Geometry',["w","h","left","top"])
        dw = app.primaryScreen()
        self.display_geometry = Geometry(
            dw.geometry().width(),
            dw.geometry().height(),
            0,
            0
        )
        self.avaliable_geometry = Geometry(
            dw.availableGeometry().width(),
            dw.availableGeometry().height(),
            dw.availableGeometry().left(),
            dw.availableGeometry().top()
        )

    @timer
    def dominant_colors(self,image): 
        """
        Input: PIL image
        Output: A list of 10 colors in the image from most dominant to least dominant
        Adaptation of https://stackoverflow.com/a/3244061/7274182
        """
        num_clusters = 10

        image = image.resize((150, 150))      # optional, to reduce time
        ar = numpy.asarray(image)
        shape = ar.shape
        ar = ar.reshape(numpy.product(shape[:2]), shape[2]).astype(float)

        kmeans = sklearn.cluster.KMeans(
            n_clusters=num_clusters,
            init="k-means++",
            max_iter=20,
            random_state=1000
        ).fit(ar)
        codes = kmeans.cluster_centers_

        vecs, dist = scipy.cluster.vq.vq(ar, codes)         # assign codes
        counts, bins = numpy.histogram(vecs, len(codes))    # count occurrences

        Color = collections.namedtuple('Color',['r','g','b'])
        colors = []
        for index in numpy.argsort(counts)[::-1]:
            color_tuple = tuple([int(code) for code in codes[index]])
            colors.append(Color(*color_tuple))
        return colors                    # returns colors in order of dominance


    @staticmethod
    def color_difference(c1, c2):
        """
        Input: RGB named tuples
        Output: An aproximation of percieved color difference of two colors
        https://www.compuphase.com/cmetric.htm
        """
        r = (c1.r + c2.r)/2
        delta_r = c1.r - c2.r
        delta_g = c1.g - c2.g
        delta_b = c1.b - c2.b
        return ((2+r/256)*delta_r**2 + 4*delta_g**2 + (2 + (255-r)/256)*delta_b**2)**0.5

    @staticmethod
    def color_luminosity(color):
        min_rgb = min(color)/255
        max_rgb = max(color)/255
        return (max_rgb+min_rgb)/2

    def color_saturation(self,color): # https://medium.com/@donatbalipapp/colours-maths-90346fb5abda
        """
        Input: RGB named tuple
        Output: Saturation of the color 0-1
        """
        min_rgb = min(color)/255
        max_rgb = max(color)/255
        luminosity = self.color_luminosity(color)
        if luminosity == 0:
            return 0
        else:
            return (max_rgb-min_rgb)/(1-abs(2*luminosity - 1))

    @timer
    def gradient_background(self, image): # https://gist.github.com/weihanglo/1e754ec47fdd683a42fdf6a272904535
        def interpolate(f_co, t_co, interval):
            det_co =[(t - f) / interval for f , t in zip(f_co, t_co)]
            for i in range(interval):
                yield [round(f + det * i) for f, det in zip(f_co, det_co)]

        gradient = Image.new("RGB",self.avaliable_geometry[:2],color=0)
        draw = ImageDraw.Draw(gradient)
        dominant_colors = self.dominant_colors(image)

        """
        Determine best colours for the gradient
        Firstly get the 7 most dominant colours and pick the most saturated
        Pair the most saturated colour with the colour that has the largest percieved difference
        """

        saturations = {color:self.color_saturation(color) for color in dominant_colors[:7]}
        sorted_saturations = sorted(saturations.items(), key=lambda x: x[1], reverse=True)  # (((255,0,0),1),((100,0,0),0.5),...)

        color_differences = {
            (sorted_saturations[0][0],color):self.color_difference(sorted_saturations[0][0],color) \
            for color,_ in sorted_saturations[1:]
        }
        sorted_color_differences = sorted(color_differences.items(), key=lambda x: x[1], reverse=True)

        gradient_pair = sorted_color_differences[0][0]

        # Draw the gradient
        for i, color in enumerate(interpolate(*gradient_pair, self.avaliable_geometry.w*2)):
            draw.line([(i, 0), (0, i)], tuple(color), width=1)

        return gradient

    @timer
    def color_background(self,image):
        color = self.dominant_colors(image)[0]
        return Image.new("RGB",self.avaliable_geometry[:2],color)

    @timer
    def art_background(self,image):
        max_dim = max(self.avaliable_geometry[:2])
        art_resized = image.resize([max_dim]*2,1)
        return art_resized

    @timer
    def wallpaper_background(self,*_):
        return Image.open("images/default_wallpaper.jpg")

    def gen_foreground(self,image):
        if self.foreground_enabled:
            return image.resize([self.foreground_size]*2,1)
        else:
            return None

    def save_image(self,path,image):
        try:
            image.save(path,"JPEG",quality=95)
        except OSError:
            time.sleep(0.1)
            self.save_image(path,image)

    def paste_images(self, *layers):
        base = Image.new("RGB",self.display_geometry[:2])
        for layer in layers:
            if layer is not None:
                x = int((self.avaliable_geometry.w - layer.size[0])/2) + self.avaliable_geometry.left
                y = int((self.avaliable_geometry.h - layer.size[1])/2) + self.avaliable_geometry.top
                base.paste(layer,(x,y))
        self.save_image("images/generated_wallpaper.jpg",base)

    @timer
    def generate_wallpaper(self,image):
        if isinstance(image,Image.Image):
            background = self.gen_background(image)
            if self.blur_enabled:
                background = background.filter(ImageFilter.GaussianBlur(self.blur_strength))

            self.paste_images(
                background,
                self.gen_foreground(image),
            )
            
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

        except Exception as e:
            app_log.exception("worker error")
            if __debug__:
                raise(e)



class SettingsWindow(QtWidgets.QDialog):
    def __init__(self):
        super(SettingsWindow,self).__init__()
        self.setWindowTitle("Settings")
        self.setFixedSize(470, 0)
        if os.path.exists("assets/settings_icon.png"):
            self.setWindowIcon(QtGui.QIcon("assets/settings_icon.png"))
        
        self.main_layout = QtWidgets.QFormLayout()
        self.init_service_section()
        self.main_layout.addRow(QtWidgets.QLabel(""))
        self.init_themes_section()
        self.main_layout.addRow(QtWidgets.QLabel(""))
        self.init_layer_section()
        self.main_layout.addRow(QtWidgets.QLabel(""))
        
        # Save button
        self.save_button = QtWidgets.QPushButton("Save")
        self.save_button.clicked.connect(self.save)
        self.save_button.setDefault(True)
        self.main_layout.addRow("",self.save_button)

        try:
            self.setStyleSheet(current_theme["settings_window"])
        except KeyError:
            pass

        self.setLayout(self.main_layout)

    def init_service_section(self): # https://stackoverflow.com/questions/11826036/pyside-show-hide-layouts
        self.service_combo = QtWidgets.QComboBox()
        self.service_combo.addItems(["Spotify (recommended)","Last.fm"])
        self.service_combo.currentIndexChanged.connect(
            lambda index: self.api_keys_stacked.setCurrentIndex(index))
        index = {"spotify":0,"last.fm":1}[config["Service"]["service"]]
        self.main_layout.addRow("Service",self.service_combo)
        
        self.api_keys_stacked = QtWidgets.QStackedWidget()
        self.api_keys_stacked.setCurrentIndex(index)
        self.main_layout.addRow(self.api_keys_stacked)
        # spotify section
        self.spotify_client_id = QtWidgets.QLineEdit()
        self.spotify_client_secret = QtWidgets.QLineEdit()
        self.spotify_client_id.setPlaceholderText("Client ID")
        self.spotify_client_secret.setPlaceholderText("Client Secret")
        self.spotify_client_id.setMaxLength(32)
        self.spotify_client_secret.setMaxLength(32)
        self.spotify_client_id.setText(config["Spotify"]["client_id"])
        self.spotify_client_secret.setText(config["Spotify"]["client_secret"])

        widget = QtWidgets.QWidget()
        self.api_keys_stacked.addWidget(widget)
        layout = QtWidgets.QFormLayout()
        widget.setLayout(layout)
        layout.addRow("Client ID",self.spotify_client_id)
        layout.addRow("Client Secret",self.spotify_client_secret)

        # last.fm section
        self.lastfm_username = QtWidgets.QLineEdit()
        self.lastfm_api_key = QtWidgets.QLineEdit()
        self.lastfm_username.setPlaceholderText("Username")
        self.lastfm_api_key.setPlaceholderText("API Key")
        self.lastfm_api_key.setMaxLength(32)
        self.lastfm_username.setText(config["Last.fm"]["username"])
        self.lastfm_api_key.setText(config["Last.fm"]["api_key"])

        widget = QtWidgets.QWidget()
        self.api_keys_stacked.addWidget(widget)
        layout = QtWidgets.QFormLayout()
        widget.setLayout(layout)
        layout.addRow("Username",self.lastfm_username)
        layout.addRow("API Key",self.lastfm_api_key)

        self.service_combo.setCurrentIndex(index)
        help_link = QtWidgets.QLabel(
            f'<a href="https://github.com/jac0b-w/album-art-wallpaper#getting-started">'\
            'Where do I find API keys?</a>')
        help_link.linkActivated.connect(
            lambda link: QtGui.QDesktopServices.openUrl(QtCore.QUrl(link)))
        self.main_layout.addRow(help_link)

    def init_layer_section(self):
        self.foreground_checkbox = QtWidgets.QCheckBox()
        self.main_layout.addRow("Foreground Art",self.foreground_checkbox)
        self.foreground_checkbox.setChecked(config["Settings"].getboolean("foreground_enabled"))
        
        self.foreground_size = QtWidgets.QSpinBox()
        self.foreground_size.setRange(1,10_000)
        self.main_layout.addRow("Art Size",self.foreground_size)
        self.foreground_size.setValue(config["Settings"].getint("foreground_size"))
        self.foreground_size.setEnabled(self.foreground_checkbox.isChecked())
        self.foreground_checkbox.stateChanged.connect(
            lambda checked: self.foreground_size.setEnabled(checked))

        self.background_combo = QtWidgets.QComboBox()
        self.background_combo.addItems(["Solid","Gradient","Art", "Wallpaper"])
        self.main_layout.addRow("Background",self.background_combo)
        self.background_combo.setCurrentText(config["Settings"].get("background_type"))
        self.background_combo.currentIndexChanged.connect(self.background_setEnabled_check)

        self.blur_checkbox = QtWidgets.QCheckBox()
        self.main_layout.addRow("Background Blur",self.blur_checkbox)
        self.blur_checkbox.setChecked(config["Settings"].getboolean("blur_enabled"))
        self.blur_checkbox.stateChanged.connect(self.background_setEnabled_check)

        self.blur_strength = QtWidgets.QDoubleSpinBox()
        self.blur_strength.setRange(0.0,100.0)
        self.blur_strength.setSingleStep(0.5)
        self.main_layout.addRow("Blur Strength",self.blur_strength)
        self.blur_strength.setValue(config["Settings"].getfloat("blur_strength"))

        self.background_setEnabled_check()

    def init_themes_section(self):
        # theme selection
        self.theme_selector = QtWidgets.QComboBox()
        themes = [f[9:-3] for f in glob.glob("./themes/*.py")]
        for theme in themes:
            self.theme_selector.addItem(theme)
        self.theme_selector.setCurrentIndex(
            self.theme_selector.findText(config["Settings"]["theme"],
            QtCore.Qt.MatchFixedString)
        )
        self.main_layout.addRow("Theme",self.theme_selector)

        self.edit_theme_button = QtWidgets.QPushButton("Edit Themes")
        self.edit_theme_button.clicked.connect(self.edit_themes)
        self.main_layout.addRow("",self.edit_theme_button)

    def save(self):
        service = ["spotify","last.fm"][self.service_combo.currentIndex()]
        config["Service"]["service"] = service

        config["Spotify"]["client_id"] = self.spotify_client_id.text()
        config["Spotify"]["client_secret"] = self.spotify_client_secret.text()

        config["Last.fm"]["api_key"] = self.lastfm_api_key.text()
        config["Last.fm"]["username"] = self.lastfm_username.text()

        # layer settings
        config["Settings"]["foreground_enabled"] = str(self.foreground_checkbox.isChecked())
        config["Settings"]["foreground_size"] = str(self.foreground_size.value())
        config["Settings"]["background_type"] = self.background_combo.currentText()
        config["Settings"]["blur_enabled"] = str(self.blur_checkbox.isChecked())
        config["Settings"]["blur_strength"] = str(self.blur_strength.value())

        config["Settings"]["theme"] = self.theme_selector.currentText()

        if check_config(config):
            config.save()  # save settings.ini and services.ini
            self.close()  # close window
            QtWidgets.QApplication.exit(1)  # send restart exit code

    def edit_themes(self):
        try:
            os.startfile("themes")
        except FileNotFoundError:
            os.makedirs("themes")
            os.startfile("themes")

    def background_setEnabled_check(self):
        self.blur_checkbox.setEnabled(self.background_combo.currentIndex() in (2,3))
        self.blur_strength.setEnabled(
            self.background_combo.currentIndex() in (2,3) and self.blur_checkbox.isChecked()
        )


class SystemTrayIcon(QtWidgets.QSystemTrayIcon):
    def __init__(self, icon, parent=None):
        QtWidgets.QSystemTrayIcon.__init__(self, icon, parent)
        self.setToolTip('Album Art Wallpaper')
        self.menu = QtWidgets.QMenu(parent)
        self.cursor = QtGui.QCursor()

        try:
            self.menu.setStyleSheet(current_theme["menu"])
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
        github_link = "https://github.com/jac0b-w/album-art-wallpaper/"
        help_latest.triggered.connect(self.open_link(f"{github_link}blob/master/README.md"))
        help_current.triggered.connect(self.open_link(f"{github_link}blob/{__version__}/README.md"))

        bug_report_item = self.menu.addAction("Bug Report")
        bug_report_item.triggered.connect(self.open_link(f"{github_link}issues"))

        release_item = self.menu.addAction(f"{__version__}")
        release_item.triggered.connect(self.open_link(f"{github_link}releases"))

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
        return lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl(link))

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
            config = ConfigManager()

            try:
                with open(f"themes/{config['Settings']['theme']}.py") as f:
                    current_theme = ast.literal_eval(f.read())
            except:
                current_theme = {"settings_window":"","menu":""}

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

            check_file(
                "settings.ini",
                "services.ini",
                "assets/icon.ico",
                "assets/missing_art.jpg",
                quit_if_missing = True)
            check_file(
                "assets/settings_icon.png",
                quit_if_missing = False)

            if check_config(config):
                thread = Worker()
                thread.finished.connect(app.exit)
                thread.start()

                exit_code = app.exec_()
                thread.terminate()

            else:
                settings_window.exec_()

        except Exception as e:
            app_log.exception("main error")
            if __debug__:
                raise(e)

