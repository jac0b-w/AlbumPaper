import os, sys, time, json, glob, shutil, webbrowser, subprocess, ctypes, spotipy, urllib.request, configparser, requests
from PySide2 import QtWidgets, QtGui, QtCore
from PIL import Image
from colorthief import ColorThief


def spotify_auth():
    os.environ["CLIENT_ID"] = config["Spotify API Keys"]["CLIENT_ID"]
    os.environ["CLIENT_SECRET"] = config["Spotify API Keys"]["CLIENT_SECRET"]

    CLI_ID = os.getenv('CLIENT_ID')
    CLI_SEC = os.getenv('CLIENT_SECRET')
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
        webbrowser.open("http://localhost:5000/")
        if os.path.exists('spotify-auth.py'):
            subprocess.run(["python", "spotify-auth.py"], shell=True)
        elif os.path.exists('spotify-auth.exe'):
            subprocess.run(["start", "spotify-auth.exe"], shell=True)
    
    if os.path.exists(".cache"):
        with open(".cache", "r") as f:
            data = json.load(f)
            token = data["access_token"]

        return spotipy.Spotify(auth=token)

    else:
        tray_icon.showMessage('Authorisation Error','Please make sure you have logged in, and have valid API Keys')
        sys.exit()


def spotify_current_track(sp):
    try:
        current = sp.currently_playing()
        if current == None:
            return None
        return {
            "art_available":current["is_playing"],
            "image":current["item"]["album"]["images"][0]["url"],
            "id":current["item"]["id"]
        }
    except:
        return {"art_available":False}


def lastfm_request(payload):
    # define headers and URL
    headers = {'user-agent': "album-art-wallpaper"}
    url = 'http://ws.audioscrobbler.com/2.0/'

    # Add API key and format to the payload
    payload['api_key'] = config["Last.fm"]["api_key"]
    payload['format'] = 'json'

    response = requests.get(url, headers=headers, params=payload)
    return response


def lastfm_current_track():
    try:
        current = lastfm_request({
            "method":"user.getRecentTracks",
            "limit":1,
            "user":config["Last.fm"]["username"]
        }).json()["recenttracks"]["track"][0]
    except KeyError: # Occurs when last.fm api fails
        return None
    except:
        # occurs with poor/no connection
        return {"art_available":False}
    try:
        return {
            "art_available":str_bool(current["@attr"]["nowplaying"]),
            "image": current["image"][0]["#text"].replace("/34s",""),
            "id":current['mbid']
        }
    except: # occurs when there is no art avaliable
        return {"art_available":False}


def str_bool(string):
    string = string.lower()
    if string == "false" or string == "0":
        return False
    elif string == "true" or string == "1":
        return True


def dominant_colour(file_name):
    color_thief = ColorThief(file_name)
    # get the dominant color
    return color_thief.get_color(quality=50)


def download_image(url):
    urllib.request.urlretrieve(url, "images/album-art.jpg")


def set_wallpaper(file_name):
    abs_path = os.path.abspath(file_name)
    ctypes.windll.user32.SystemParametersInfoW(20, 0, abs_path , 0)

def generate_wallpaper(file_name): #if resize = true, then px controls the resize dimentions
    art_size = int(config["Settings"]["art_size"])
    x,y = (ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1))
    background = Image.new('RGB', (x,y), dominant_colour(file_name))
    art = Image.open(file_name)
    art = art.resize((art_size,art_size),1)
    background.paste(art,(int((x-art.size[0])/2),int((y-art.size[1])/2)))
    background.save("images/generated_wallpaper.png")


def set_default_wallpaper():
    cached_folder = os.path.expandvars(r'%APPDATA%\Microsoft\Windows\Themes\CachedFiles\*')
    list_of_files = glob.glob(cached_folder)
    latest_file = max(list_of_files, key=os.path.getctime)
    shutil.copy(latest_file, "images/default_wallpaper.jpg")


class Worker(QtCore.QThread):
    # Worker thread
    @QtCore.Slot()
    def run(self):
        if using_spotify:
            sp = spotify_auth()

        previous_wallpaper = None
        request_interval = int(config["Settings"]["request_interval"])

        while True:
            time.sleep(request_interval)
            if using_spotify:
                current = spotify_current_track(sp)
                if current is None:
                    sp = spotify_auth()
                    continue
            else:
                current = lastfm_current_track()
                if current is None:
                    continue
            if current["art_available"]:
                if current["id"] != previous_wallpaper:
                    download_image(current["image"])
                    generate_wallpaper("images/album-art.jpg")
                    set_wallpaper("images/generated_wallpaper.png")
                    previous_wallpaper = current["id"]

            elif previous_wallpaper is not None:
                set_wallpaper("images/default_wallpaper.jpg")
                previous_wallpaper = None

            

class SystemTrayIcon(QtWidgets.QSystemTrayIcon):
    def __init__(self, icon, parent=None):
        QtWidgets.QSystemTrayIcon.__init__(self, icon, parent)
        self.setToolTip(f'Album Art Wallpaper')
        menu = QtWidgets.QMenu(parent)

        default_wallpaper_item = menu.addAction("Set Default Wallpaper")
        default_wallpaper_item.triggered.connect(self.set_default_wallpaper)

        settings_item = menu.addAction("Settings")
        settings_item.triggered.connect(self.settings)

        about_item = menu.addAction("Help")
        about_item.triggered.connect(self.open_readme)

        bug_report_item = menu.addAction("Bug Report")
        bug_report_item.triggered.connect(self.bug_report)

        release_item = menu.addAction("v1.1.3")
        release_item.triggered.connect(self.open_releases)

        exit_ = menu.addAction("Quit")
        exit_.triggered.connect(self.exit)

        menu.addSeparator()
        self.setContextMenu(menu)
    #     self.activated.connect(self.onTrayIconActivated)
    
    # def onTrayIconActivated(self, reason):
    #     # Action on double click
    #     if reason == self.DoubleClick:
    #         pass
    #     if reason == self.Trigger:
    #         print("single click")

    def set_default_wallpaper(self):
        set_default_wallpaper()
        tray_icon.showMessage('Saved','Wallpaper saved as default')

    def settings(self):
        subprocess.Popen(["notepad.exe","config.ini"]) # subprocess.Popen is non-blocking

    def open_readme(self):
        webbrowser.open("https://github.com/jac0b-w/album-art-wallpaper/blob/master/README.md")

    def bug_report(self):
        webbrowser.open("https://github.com/jac0b-w/album-art-wallpaper/issues/new")

    def open_releases(self):
        webbrowser.open("https://github.com/jac0b-w/album-art-wallpaper/releases/latest")

    def exit(self):
        set_wallpaper("images/default_wallpaper.jpg")
        sys.exit()

config = configparser.ConfigParser()
config.read('config.ini')






if not os.path.exists('images'):
    os.makedirs('images')
if not os.path.exists("images/default_wallpaper.jpg"):
    set_default_wallpaper()

app = QtWidgets.QApplication(sys.argv)

w = QtWidgets.QWidget()
tray_icon = SystemTrayIcon(QtGui.QIcon("icon.ico"), w)
tray_icon.show()



if config["Service"]["service"].lower() == "spotify":
    using_spotify = True
elif config["Service"]["service"].lower().replace(".","") == "lastfm":
    using_spotify = False
else:
    tray_icon.showMessage('No sevice set','Set the service in settings to spotify or last.fm')
    subprocess.run(["notepad.exe","config.ini"])
    sys.exit()



if using_spotify:
    if len(config["Spotify API Keys"]["CLIENT_SECRET"]) != 32 or len(config["Spotify API Keys"]["CLIENT_ID"]) != 32:
        tray_icon.showMessage('Invalid API Keys','Set valid Spotify API Keys')
        subprocess.run(["notepad.exe","config.ini"])
        sys.exit()


else:  # using last.fm
    while len(config["Last.fm"]["api_key"]) != 32:
        tray_icon.showMessage('Invalid API Key','Set a valid Last.fm API key')
        subprocess.run(["notepad.exe","config.ini"])
        sys.exit()


thread = Worker()
thread.finished.connect(app.exit)
thread.start()

sys.exit(app.exec_())
