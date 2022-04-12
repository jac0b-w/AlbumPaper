import hashlib, threading, spotipy
from config import ConfigManager, ConfigValidationError
from typing import Callable
from PySide2 import QtWidgets

class SpotifyAuth:
    def __init__(self, toast: Callable):
        self.toast = toast
        self.authorize()

    def authorize(self):
        client_id = ConfigManager.services["spotify"]["client_id"]
        client_secret = ConfigManager.services["spotify"]["client_secret"]

        # Easier than deleting the .cache each time keys change and means
        # no relogin after switching to previous keys
        hasher = hashlib.shake_128()
        hasher.update((client_id + client_secret).encode("UTF-8"))
        hashed_keys = hasher.hexdigest(3)

        self.sp_oauth = spotipy.SpotifyOAuth(
            client_id,
            client_secret,
            redirect_uri="http://localhost:8080/",
            scope="user-read-currently-playing",
            cache_path=f".cache-{hashed_keys}",
            show_dialog=True,
        )

        try:
            self.token_info = self.sp_oauth.get_access_token(as_dict=True)
            token = self.token_info["access_token"]
        except spotipy.oauth2.SpotifyOauthError as e:
            self.toast("Authentication Error", e.error_description)
            ConfigManager.services["spotify"]["client_secret"] = ""
            try:
                ConfigManager.save()
            except ConfigValidationError as e:
                self.toast("Set valid Spotify client secret", "")
            threading.Event().wait(3)
            QtWidgets.QApplication.exit(0)

        try:
            self.api = spotipy.Spotify(auth=token)
        except Exception as e:
            raise e

    def refresh_token(self):
        try:
            if self.sp_oauth.is_token_expired(token_info=self.token_info):
                self.token_info = self.sp_oauth.refresh_access_token(
                    self.token_info["refresh_token"]
                )
                token = self.token_info["access_token"]
                self.api = spotipy.Spotify(auth=token)
                print("TOKEN REFRESHED")
        except:
            print("FAILED TO REFRESH TOKEN")
