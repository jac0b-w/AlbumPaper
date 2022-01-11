"""
Classes in this file:
  SystemTrayIcon
  SettingsWindow
"""

from PySide2 import QtWidgets, QtGui, QtCore
import os, glob

from config import ConfigManager, ConfigValidationError
from wallpaper import Wallpaper


class SystemTrayIcon(QtWidgets.QSystemTrayIcon):
    def __init__(self, icon, parent, signal, version):
        QtWidgets.QSystemTrayIcon.__init__(self, icon, parent)
        self.setToolTip("AlbumPaper")
        self.context_menu = QtWidgets.QMenu(parent)
        self.signal = signal
        self.VERSION = version

        try:
            self.context_menu.setStyleSheet(ConfigManager.theme()["menu"])
        except KeyError:
            pass

        default_wallpaper_item = self.context_menu.addAction(
            QtGui.QIcon("assets/wallpaper.png"), "Set Default Wallpaper"
        )
        default_wallpaper_item.triggered.connect(self.set_default_wallpaper)

        self.context_menu.addSeparator()

        settings_item = self.context_menu.addAction(
            QtGui.QIcon("assets/settings_icon.png"), "Settings"
        )
        settings_item.triggered.connect(self.settings)
        self.settings_window = SettingsWindow(self)

        self.context_menu.addSeparator()

        self.help_menu = self.context_menu.addMenu(
            QtGui.QIcon("assets/help.png"), "Help"
        )
        help_latest = self.help_menu.addAction("Lastest Release")
        help_current = self.help_menu.addAction("This Release")
        github_link = "https://github.com/jac0b-w/AlbumPaper/"
        help_latest.triggered.connect(
            self.open_link(f"{github_link}blob/master/README.md")
        )
        help_current.triggered.connect(
            self.open_link(f"{github_link}blob/{self.VERSION}/README.md")
        )

        bug_report_item = self.context_menu.addAction(
            QtGui.QIcon("assets/bug_report.png"), "Bug Report"
        )
        bug_report_item.triggered.connect(self.open_link(f"{github_link}issues"))

        release_item = self.context_menu.addAction(
            QtGui.QIcon("assets/update.png"), f"{self.VERSION}"
        )
        release_item.triggered.connect(self.open_link(f"{github_link}releases"))

        self.context_menu.addSeparator()

        self.pause_item = self.context_menu.addAction(
            QtGui.QIcon("assets/pause.png"), "Pause"
        )
        self.pause_item.triggered.connect(self.toggle_pause)
        self.is_paused = False

        restart_item = self.context_menu.addAction(
            QtGui.QIcon("assets/restart.png"), "Restart"
        )
        restart_item.triggered.connect(self.exit(1))

        exit_item = self.context_menu.addAction(QtGui.QIcon("assets/close.png"), "Quit")
        exit_item.triggered.connect(self.exit(0))

        self.setContextMenu(self.context_menu)
        self.activated.connect(self.clicked)

        self.messageClicked.connect(
            self.open_link("https://github.com/jac0b-w/AlbumPaper/releases")
        )

    def clicked(self, reason):
        # self.Trigger is left click
        if reason == self.DoubleClick:
            self.toggle_pause()

    def settings(self):
        self.settings_window.show()
        self.settings_window.activateWindow()

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        pause_text = {True: "Continue", False: "Pause"}[self.is_paused]
        pause_icon = {
            False: QtGui.QIcon("assets/pause.png"),
            True: QtGui.QIcon("assets/play.png"),
        }[self.is_paused]
        self.pause_item.setText(pause_text)
        self.pause_item.setIcon(pause_icon)
        icon = {False: "enabled", True: "disabled"}[self.is_paused]
        self.setIcon(QtGui.QIcon(f"assets/{icon}.png"))
        self.signal.pause_state.emit(self.is_paused)

    def set_default_wallpaper(self):
        Wallpaper.set_default()
        self.showMessage("Saved", "Wallpaper saved as default")

    def open_link(self, link):
        return lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl(link))

    def exit(self, exit_code):
        def exit_function():
            Wallpaper.set(is_default=True)
            QtWidgets.QApplication.exit(exit_code)

        return exit_function


class SettingsWindow(QtWidgets.QDialog):
    def __init__(self, tray_icon):
        super(SettingsWindow, self).__init__()
        self.tray_icon = tray_icon
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
        self.main_layout.addRow("", self.save_button)

        try:
            self.setStyleSheet(ConfigManager.theme()["settings_window"])
        except KeyError:
            pass

        self.setLayout(self.main_layout)

    def init_service_section(
        self,
    ):  # https://stackoverflow.com/questions/11826036/pyside-show-hide-layouts
        self.service_combo = QtWidgets.QComboBox()
        self.service_combo.addItems(["Spotify (recommended)", "Last.fm"])
        self.service_combo.currentIndexChanged.connect(
            lambda index: self.api_keys_stacked.setCurrentIndex(index)
        )
        index = {"spotify": 0, "last.fm": 1}[ConfigManager.settings["service"]["name"]]
        self.main_layout.addRow("Service", self.service_combo)

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
        self.spotify_client_id.setText(ConfigManager.services["spotify"]["client_id"])
        self.spotify_client_secret.setText(
            ConfigManager.services["spotify"]["client_secret"]
        )

        widget = QtWidgets.QWidget()
        self.api_keys_stacked.addWidget(widget)
        layout = QtWidgets.QFormLayout()
        widget.setLayout(layout)
        layout.addRow("Client ID", self.spotify_client_id)
        layout.addRow("Client Secret", self.spotify_client_secret)

        # last.fm section
        self.lastfm_username = QtWidgets.QLineEdit()
        self.lastfm_api_key = QtWidgets.QLineEdit()
        self.lastfm_username.setPlaceholderText("Username")
        self.lastfm_api_key.setPlaceholderText("API Key")
        self.lastfm_api_key.setMaxLength(32)
        self.lastfm_username.setText(ConfigManager.services["last.fm"]["username"])
        self.lastfm_api_key.setText(ConfigManager.services["last.fm"]["api_key"])

        widget = QtWidgets.QWidget()
        self.api_keys_stacked.addWidget(widget)
        layout = QtWidgets.QFormLayout()
        widget.setLayout(layout)
        layout.addRow("Username", self.lastfm_username)
        layout.addRow("API Key", self.lastfm_api_key)

        self.service_combo.setCurrentIndex(index)
        help_link = QtWidgets.QLabel(
            f'<a href="https://github.com/jac0b-w/AlbumPaper/wiki/Getting-API-Keys">'
            "Where do I find API keys?</a>"
        )
        help_link.linkActivated.connect(
            lambda link: QtGui.QDesktopServices.openUrl(QtCore.QUrl(link))
        )
        self.main_layout.addRow(help_link)

    def init_layer_section(self):
        self.foreground_checkbox = QtWidgets.QCheckBox()
        self.main_layout.addRow("Foreground Art", self.foreground_checkbox)
        self.foreground_checkbox.setChecked(
            ConfigManager.settings["foreground"]["enabled"]
        )

        self.foreground_size = QtWidgets.QSpinBox()
        self.foreground_size.setRange(1, 10_000)
        self.main_layout.addRow("Art Size", self.foreground_size)
        self.foreground_size.setValue(ConfigManager.settings["foreground"]["size"])
        self.foreground_size.setEnabled(self.foreground_checkbox.isChecked())
        self.foreground_checkbox.stateChanged.connect(
            lambda checked: self.foreground_size.setVisible(checked)
        )

        self.background_combo = QtWidgets.QComboBox()
        self.background_combo.addItems(
            [
                "Solid",
                "Linear Gradient",
                "Radial Gradient",
                "Art",
                "Wallpaper",
                "Random",
            ]
        )
        self.main_layout.addRow("Background", self.background_combo)
        self.background_combo.setCurrentText(
            ConfigManager.settings["background"]["type"]
        )
        self.background_combo.currentIndexChanged.connect(
            self.background_setEnabled_check
        )

        self.blur_checkbox = QtWidgets.QCheckBox()
        self.main_layout.addRow("Background Blur", self.blur_checkbox)
        self.blur_checkbox.setChecked(
            ConfigManager.settings["background"]["blur_enabled"]
        )
        self.blur_checkbox.stateChanged.connect(self.background_setEnabled_check)

        self.blur_strength = QtWidgets.QDoubleSpinBox()
        self.blur_strength.setRange(0.5, 100.0)
        self.blur_strength.setSingleStep(0.5)
        self.main_layout.addRow("Blur Strength", self.blur_strength)
        self.blur_strength.setValue(
            ConfigManager.settings["background"]["blur_strength"]
        )

        self.background_setEnabled_check()

    def init_themes_section(self):
        # theme selection
        self.theme_selector = QtWidgets.QComboBox()
        themes = [f[9:-3] for f in glob.glob("./themes/*.py")]
        for theme in themes:
            self.theme_selector.addItem(theme)
        self.theme_selector.setCurrentIndex(
            self.theme_selector.findText(
                ConfigManager.settings["theme"]["name"], QtCore.Qt.MatchFixedString
            )
        )
        self.main_layout.addRow("Theme", self.theme_selector)

        self.edit_theme_button = QtWidgets.QPushButton("Edit Themes")
        self.edit_theme_button.clicked.connect(self.edit_themes)
        self.main_layout.addRow("", self.edit_theme_button)

    def save(self):
        service = ["spotify", "last.fm"][self.service_combo.currentIndex()]
        ConfigManager.settings["service"]["name"] = service

        ConfigManager.services["spotify"]["client_id"] = self.spotify_client_id.text()
        ConfigManager.services["spotify"][
            "client_secret"
        ] = self.spotify_client_secret.text()

        ConfigManager.services["last.fm"]["api_key"] = self.lastfm_api_key.text()
        ConfigManager.services["last.fm"]["username"] = self.lastfm_username.text()

        # layer settings
        ConfigManager.settings["foreground"][
            "enabled"
        ] = self.foreground_checkbox.isChecked()
        ConfigManager.settings["foreground"]["size"] = self.foreground_size.value()
        ConfigManager.settings["background"][
            "type"
        ] = self.background_combo.currentText()
        ConfigManager.settings["background"][
            "blur_enabled"
        ] = self.blur_checkbox.isChecked()
        ConfigManager.settings["background"][
            "blur_strength"
        ] = self.blur_strength.value()

        ConfigManager.settings["theme"]["name"] = self.theme_selector.currentText()

        try:
            ConfigManager.save()  # save settings.ini and services.ini
        except ConfigValidationError as e:
            self.tray_icon.showMessage(e.message, "")
        else:
            self.accept()
            QtWidgets.QApplication.exit(1)  # send restart exit code

    def edit_themes(self):
        try:
            os.startfile("themes")
        except FileNotFoundError:
            os.makedirs("themes")
            os.startfile("themes")

    def background_setEnabled_check(self):
        """
        Show blur option only when 'Wallpaper' or 'Art' background options
        are selected
        """
        self.blur_checkbox.setEnabled(self.background_combo.currentIndex() in (2, 3))
        self.blur_strength.setEnabled(
            self.background_combo.currentIndex() in (2, 3)
            and self.blur_checkbox.isChecked()
        )
