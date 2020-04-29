import os, sys, time, json, glob, shutil, webbrowser, subprocess, ctypes, spotipy, urllib.request, configparser
from PySide2 import QtWidgets, QtGui, QtCore
from PIL import Image, ImageDraw
from colorthief import ColorThief

def str_bool(string):
    string = string.lower()
    if string == "false" or string == "0":
        return False
    elif string == "true" or string == "1":
        return True

def current_track(sp):
    current = sp.currently_playing()
    try:
        return {
            "art_available":current["is_playing"],
            "image":current["item"]["album"]["images"][0]["url"],
            "id":current["item"]["id"]
        }
    except (TypeError, IndexError):
        return {"art_available":False}


def dominant_colour(file_name):
    color_thief = ColorThief(file_name)
    # get the dominant color
    return color_thief.get_color(quality=50)

def download_image(url):
    urllib.request.urlretrieve(url, "images/spotify-album-art.jpg")

def set_wallpaper(file_name):
    abs_path = os.path.abspath(file_name)
    ctypes.windll.user32.SystemParametersInfoW(20, 0, abs_path , 0)

def generate_wallpaper(file_name,resize):
    x,y = (ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1))
    background = Image.new('RGB', (x,y), dominant_colour(file_name))
    art = Image.open(file_name)
    if resize:
        art = art.resize((min(x,y),min(x,y)),0)
    background.paste(art,(int((x-art.size[0])/2),int((y-art.size[1])/2)))
    background.save("images/generated_wallpaper.png")

class Worker(QtCore.QThread):
    # Worker thread
    @QtCore.Slot()
    def run(self):
        previous_wallpaper = None
        request_interval = int(config["Settings"]["request_interval"])
        while True:
            current = current_track(sp)
            if current["art_available"]:

                if current["id"] != previous_wallpaper:
                    download_image(current["image"])
                    generate_wallpaper("images/spotify-album-art.jpg",str_bool(config["Settings"]["resize_art"]))
                    set_wallpaper("images/generated_wallpaper.png")
                    previous_wallpaper = current["id"]

            elif previous_wallpaper != None:
                set_wallpaper("images/default_wallpaper.jpg")
                previous_wallpaper = None

            time.sleep(request_interval)

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

        release_item = menu.addAction("v1.0")
        release_item.triggered.connect(self.open_releases)

        exit_ = menu.addAction("Quit")
        exit_.triggered.connect(self.exit)

        menu.addSeparator()
        self.setContextMenu(menu)
        # self.activated.connect(self.onTrayIconActivated)


    # def onTrayIconActivated(self, reason):
    #     # Action on double click
    #     if reason == self.DoubleClick:
    #         print("double click")
    #     if reason == self.Trigger:
    #         print("single click")

    def set_default_wallpaper(self):
        cached_folder = os.path.expandvars(r'%APPDATA%\Microsoft\Windows\Themes\CachedFiles\*')
        list_of_files = glob.glob(cached_folder)
        latest_file = max(list_of_files, key=os.path.getctime)
        shutil.copy(latest_file, "images/default_wallpaper.jpg")
        tray_icon.showMessage('Saved','Wallpaper saved as default')


    def settings(self):
        os.system("notepad.exe config.ini")

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

if config["API Keys"]["CLIENT_SECRET"] == "<Your Client ID>" or config["API Keys"]["CLIENT_SECRET"] == "<Your Client Secret>":
    subprocess.call(["notepad.exe","config.ini"])
    quit()

subprocess.run(["python","spotify_auth.py"])

with open(".cache","r") as f:
    data = json.load(f)
    token = data["access_token"]

if not os.path.exists('images'):
    os.makedirs('images')


sp = spotipy.Spotify(auth=token)

app = QtWidgets.QApplication(sys.argv)

w = QtWidgets.QWidget()
tray_icon = SystemTrayIcon(QtGui.QIcon("icon.ico"), w)
tray_icon.show()

thread = Worker()
thread.finished.connect(app.exit)
thread.start()

sys.exit(app.exec_())