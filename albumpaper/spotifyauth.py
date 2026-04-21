import contextlib
import threading
from collections.abc import Callable

import spotipy
import xxhash
from configuration import AppPaths, ConfigManager
from PySide6 import QtWidgets


class SpotifyAuth:
    def __init__(self, toast: Callable) -> None:
        self.toast = toast
        self.authorize()

    def authorize(self) -> None:
        client_id = ConfigManager.services["spotify"]["client_id"]
        client_secret = ConfigManager.services["spotify"]["client_secret"]

        # Easier than deleting the .cache each time keys change and means
        # no relogin after switching to previous keys
        hashed_keys = xxhash.xxh32(
            (client_id + client_secret).encode("UTF-8"),
        ).hexdigest()

        spotipy_cache_path = (
            AppPaths.PROJECT_ROOT / "cache" / f".spotipy-cache-{hashed_keys}"
        )
        self.sp_oauth = spotipy.SpotifyOAuth(
            client_id,
            client_secret,
            redirect_uri=ConfigManager.settings["service"]["redirect_uri"],
            scope="user-read-currently-playing user-read-playback-state",
            cache_path=spotipy_cache_path,
            show_dialog=True,
        )

        try:
            self.token_info = self.sp_oauth.get_access_token(as_dict=True)
            token = self.token_info["access_token"]
        except spotipy.oauth2.SpotifyOauthError as e:
            self.toast("Authentication Error", e.error_description)
            ConfigManager.services["spotify"]["client_secret"] = ""
            ConfigManager.save_internal_state()
            ConfigManager.save_widget_state()

            threading.Event().wait(3)
            QtWidgets.QApplication.exit(1)

        with contextlib.suppress(BaseException):
            self.api = spotipy.Spotify(auth=token)

    def refresh_token(self) -> None:
        try:
            if self.sp_oauth.is_token_expired(token_info=self.token_info):
                self.token_info = self.sp_oauth.refresh_access_token(
                    self.token_info["refresh_token"],
                )
                token = self.token_info["access_token"]
                self.api = spotipy.Spotify(auth=token)
                print("TOKEN REFRESHED")
        except:  # noqa: E722
            print("FAILED TO REFRESH TOKEN")
