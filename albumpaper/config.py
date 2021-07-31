import configparser, ast


class Config:
    """
    Usage:

    config = Config()

    config.spotify["client_secret"]
    config.lastfm["api_key"]
    config.settings["service"]
    config.theme["menu"]

    """

    def __init__(self):
        self._services_config = configparser.ConfigParser()
        self._services_config.read("services.ini")
        self._settings_config = configparser.ConfigParser()
        self._settings_config.read("settings.ini")

        self.settings = self._settings_config["Settings"]
        self.spotify = self._services_config["Spotify"]
        self.lastfm = self._services_config["Last.fm"]

        self.update_theme()

    def update_theme(self):
        try:
            with open(f"themes/{self.settings['theme']}.py") as f:
                self.theme = ast.literal_eval(f.read())
        except FileNotFoundError:
            self.theme = {}

    def save(self):
        with open("settings.ini", "w") as f:
            self._settings_config.write(f)
        with open("services.ini", "w") as f:
            self._services_config.write(f)
        self.update_theme()

    def check_valid(self, tray_icon):
        # invalid spotify keys
        if self.settings["service"].lower() == "spotify":
            if (
                len(self.spotify["client_secret"]) != 32
                or len(self.spotify["client_id"]) != 32
            ):
                print("INVALID SPOTIFY KEY")
                tray_icon.showMessage("Invalid API Keys", "Set valid Spotify API Keys")
                return False

        # invalid last.fm key
        elif self.settings["service"].lower().replace(".", "") == "lastfm":
            if len(self.lastfm["api_key"]) != 32:
                tray_icon.showMessage("Invalid API Key", "Set a valid Last.fm API key")
                return False

        # If a service isn't set
        else:
            tray_icon.showMessage(
                "No sevice set", "Set the service in settings to spotify or last.fm"
            )
            return False

        return True  # valid settings file


config = Config()
