from pathlib import Path
from typing import TYPE_CHECKING, Self

import requests
from configuration import AppPaths, ConfigManager
from packaging.version import Version
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from wallpaper import BackgroundType, WindowsWallpaper

if TYPE_CHECKING:
    from collections.abc import Callable

    from albumpaper import PauseStateManager

VERSION = Version("v4.2.0")


class SystemTrayIcon(QtWidgets.QSystemTrayIcon):
    def __init__(
        self,
        icon: QtGui.QIcon,
        parent: QtWidgets.QWidget,
        signal: QtCore.Signal,
        pause_state_manager: PauseStateManager,
    ) -> None:
        super().__init__(icon, parent)
        self.setToolTip("AlbumPaper")
        self.context_menu = QtWidgets.QMenu(parent)
        self.signal = signal
        self.pause_state_manager = pause_state_manager

        if QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark:
            self.icon_color = "white"
        else:
            self.icon_color = "black"

        default_wallpaper_item = self.context_menu.addAction(
            QtGui.QIcon(f"assets/icons/{self.icon_color}/wallpaper.png"),
            "Set Default Wallpaper",
        )
        default_wallpaper_item.triggered.connect(self.set_default_wallpaper)

        self.context_menu.addSeparator()

        settings_item = self.context_menu.addAction(
            QtGui.QIcon(f"assets/icons/{self.icon_color}/settings.png"),
            "Settings",
        )
        settings_item.triggered.connect(self.settings)
        self.settings_window = SettingsWindow(self)
        ConfigManager.init_widgets()

        latest_version = self.latest_stable_update()

        self.messageClicked.connect(
            self.open_link("https://github.com/jac0b-w/AlbumPaper/releases"),
        )

        if latest_version > VERSION:
            self.context_menu.addSeparator()

            release_item = self.context_menu.addAction(
                QtGui.QIcon(f"assets/icons/{self.icon_color}/update.png"),
                f"Update avaliable (v{latest_version})",
            )
            release_item.triggered.connect(
                self.open_link(
                    "https://www.github.com/jac0b-w/AlbumPaper/releases/latest",
                ),
            )

            self.showMessage("New update", f"Update v{latest_version} available")

        self.context_menu.addSeparator()

        self.pause_item = self.context_menu.addAction(
            QtGui.QIcon(f"assets/icons/{self.icon_color}/pause.png"),
            "Pause",
        )
        self.pause_item.triggered.connect(self.toggle_pause)

        restart_item = self.context_menu.addAction(
            QtGui.QIcon(f"assets/icons/{self.icon_color}/restart.png"),
            "Restart",
        )
        restart_item.triggered.connect(self.exit(1))

        exit_item = self.context_menu.addAction(
            QtGui.QIcon(f"assets/icons/{self.icon_color}/close.png"),
            "Quit",
        )
        exit_item.triggered.connect(self.exit(0))

        self.setContextMenu(self.context_menu)
        self.activated.connect(self.clicked)

    def clicked(self, reason: QtWidgets.QSystemTrayIcon.ActivationReason) -> None:
        # self.Trigger is left click
        if reason == self.ActivationReason.DoubleClick:
            self.toggle_pause()

    def settings(self) -> None:
        self.settings_window.show()
        self.settings_window.activateWindow()

    def toggle_pause(self) -> None:
        self.pause_state_manager.toggle_pause()

    @QtCore.Slot(str)
    def pause_state(self, state: str) -> None:
        options = {
            "disabled": {"text": "Continue", "icon": "play", "enabled": True},
            "enabled": {"text": "Pause", "icon": "pause", "enabled": True},
            "battery_saver": {
                "text": "Battery Saving",
                "icon": "battery_saver",
                "enabled": False,
            },
        }[state]

        self.pause_item.setText(options["text"])
        self.pause_item.setIcon(
            QtGui.QIcon(f"assets/icons/{self.icon_color}/{options['icon']}.png"),
        )
        self.pause_item.setEnabled(options["enabled"])

        self.setIcon(QtGui.QIcon(f"assets/icons/{state}.png"))

    def set_default_wallpaper(self) -> None:
        WindowsWallpaper.cache_current()
        self.showMessage("Saved", "Wallpaper saved as default")

    def open_link(self, link: str) -> Callable:
        return lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl(link))

    def exit(self, exit_code: int) -> Callable:
        def exit_function() -> None:
            WindowsWallpaper.set_default_wallpaper()
            QtWidgets.QApplication.exit(exit_code)

        return exit_function

    def latest_stable_update(self) -> Version:
        if not ConfigManager.settings["updates"]["check_for_updates"]:
            return VERSION

        try:
            response = requests.get(
                "https://api.github.com/repos/jac0b-w/AlbumPaper/releases/latest",
                timeout=1,
            )
            latest_version: str = response.json()["tag_name"]
        except:  # noqa: E722
            return VERSION
        if any(substring in latest_version for substring in ["alpha", "beta"]):
            return VERSION

        if Version(latest_version) > VERSION:
            return Version(latest_version)

        return VERSION


class SettingsWindow(QtWidgets.QWidget):
    def __init__(self, tray_icon: QtWidgets.QSystemTrayIcon) -> None:
        super().__init__()
        self.tray_icon = tray_icon
        self.setWindowTitle("Settings")
        # self.setFixedSize(570, 0)

        if QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark:
            settings_icon_path = "assets/icons/white/settings.png"
        else:
            settings_icon_path = "assets/icons/black/settings.png"

        if Path(settings_icon_path).exists():
            self.my_icon = QtGui.QIcon(settings_icon_path)
            self.setWindowIcon(self.my_icon)

        self.main_layout = QtWidgets.QHBoxLayout()

        self.main_layout.setContentsMargins(0, 0, 0, 0)

        sidebar = Sidebar(self)
        general_settings = GeneralSettings(self)
        wallpaper_settings = WallpaperSettings(self)
        service_settings = ServiceSettings(self)

        self.main_layout.addWidget(sidebar)
        self.settings_pages = QtWidgets.QStackedWidget()
        self.main_layout.addWidget(self.settings_pages)

        self.settings_pages.addWidget(general_settings)
        self.settings_pages.addWidget(wallpaper_settings)
        self.settings_pages.addWidget(service_settings)

        self.setLayout(self.main_layout)

    def closeEvent(self, event: QtCore.QEvent) -> None:
        self.save(event)

    def save(self, event: QtCore.QEvent) -> None:
        err_message = ConfigManager.validate_service()
        print(err_message)
        if err_message:
            self.tray_icon.showMessage(err_message, "")
            event.ignore()
        else:
            ConfigManager.save_widget_state()
            QtWidgets.QApplication.exit(1)  # send restart exit code

    def openEvent(self, _event: QtCore.QEvent) -> None:
        if ConfigManager.validate_service():
            self.settings_pages.setCurrentIndex(2)


class GeneralSettings(QtWidgets.QWidget):
    def __init__(self, parent: Self | None = None) -> None:
        super().__init__(parent)

        self.info_panel = QtWidgets.QWidget()
        self.info_panel.setLayout(QtWidgets.QVBoxLayout())
        self.info_panel.layout().setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.info_panel.setStyleSheet("background-color; rgba(128, 128, 128, 20)")

        ap_label = QtWidgets.QLabel("AlbumPaper")
        ap_label.setStyleSheet("font-size: 36px;")

        gh_link = "https://github.com/jac0b-w/AlbumPaper"
        links_label = QtWidgets.QLabel(
            f"""<a href="{gh_link}">GitHub</a><br>
                <a href="{gh_link}/releases">Releases</a><br>
                <a href="{gh_link}/issues">Report a bug</a><br>
                <a href="https://www.buymeacoffee.com/jac0b">Support AlbumPaper</a>""",
        )
        links_label.setOpenExternalLinks(True)

        self.info_panel.layout().addWidget(ap_label)
        self.info_panel.layout().addWidget(links_label)

        self.default_wallpaper_widget = DefaultWallpaperPreview(self)

        cache_size_label = QtWidgets.QLabel("Cache Size (MB)")
        cache_size_label.setToolTip(
            "Larger cache size may lower wallpaper generation time",
        )

        self.cache_size_spinbox = ConfigManager.register(
            ("settings", "cache", "size"),
            QtWidgets.QSpinBox(minimum=3, maximum=100),
        )

        self.check_updates_checkbox = ConfigManager.register(
            ("settings", "updates", "check_for_updates"),
            QtWidgets.QCheckBox(),
        )

        self.battery_saver_checkbox = ConfigManager.register(
            ("settings", "power", "disable_on_battery_saver"),
            QtWidgets.QCheckBox(),
        )

        # layout
        self.setLayout(QtWidgets.QGridLayout())
        self.layout().setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        # info panel
        self.layout().addWidget(self.info_panel, 0, 0, 1, 2)
        # settins
        self.layout().addWidget(QtWidgets.QLabel("Default Wallpaper"), 1, 0)
        self.layout().addWidget(self.default_wallpaper_widget, 1, 1)
        self.layout().addWidget(cache_size_label, 2, 0)
        self.layout().addWidget(self.cache_size_spinbox, 2, 1)
        self.layout().addWidget(QtWidgets.QLabel("Check for updates"), 3, 0)
        self.layout().addWidget(self.check_updates_checkbox, 3, 1)
        self.layout().addWidget(QtWidgets.QLabel("Pause on Battery Saver"), 4, 0)
        self.layout().addWidget(self.battery_saver_checkbox, 4, 1)


class DefaultWallpaperPreview(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.label = QtWidgets.QLabel(self)

        self.update_pixmap()
        self.setFixedSize(self.pixmap.size())

        self.overlay = QtWidgets.QWidget(self)
        self.overlay.setFixedSize(self.pixmap.size())
        self.overlay.setStyleSheet("background-color: rgba(0, 0, 0, 150);")
        self.overlay.hide()

        # Buttons inside the overlay
        set_current_btn = QtWidgets.QPushButton("Set to Current")

        color = set_current_btn.palette().color(set_current_btn.backgroundRole())

        set_current_btn.setFixedWidth(100)
        set_current_btn.setStyleSheet(
            f"background-color:rgba({color.red()},{color.green()},{color.blue()},255);",
        )

        set_current_btn.clicked.connect(self.set_default_wallpaper)

        layout = QtWidgets.QHBoxLayout(self.overlay)
        layout.setAlignment(Qt.AlignCenter)

        layout.addWidget(set_current_btn)

    def enterEvent(self, _event: QtCore.QEvent) -> None:
        self.overlay.show()

    def leaveEvent(self, _event: QtCore.QEvent) -> None:
        self.overlay.hide()

    def showEvent(self, event: QtCore.QEvent) -> None:
        self.update_pixmap()
        super().showEvent(event)

    def update_pixmap(self) -> None:
        w = 320
        self.pixmap = QtGui.QPixmap(AppPaths.DEFAULT_WALLPAPER).scaledToWidth(
            w,
            Qt.SmoothTransformation,
        )
        self.label.setPixmap(self.pixmap)

    def set_default_wallpaper(self) -> None:
        WindowsWallpaper.cache_current()
        self.update_pixmap()


class WallpaperSettings(QtWidgets.QWidget):
    def __init__(self, parent: Self | None = None) -> None:
        super().__init__(parent)

        layer_tabs = QtWidgets.QTabWidget()

        foreground_widget = QtWidgets.QWidget()
        foreground_layout = QtWidgets.QVBoxLayout()
        foreground_layout.setAlignment(QtCore.Qt.AlignTop)
        foreground_widget.setLayout(foreground_layout)
        foreground_layout.addWidget(ForegroundTab())

        layer_tabs.addTab(BackgroundTab(), "Background")
        layer_tabs.addTab(foreground_widget, "Foreground")

        self.main_layout = QtWidgets.QFormLayout()

        self.main_layout.addRow(layer_tabs)

        self.setLayout(self.main_layout)


class BackgroundTab(QtWidgets.QWidget):
    def __init__(self) -> None:
        super().__init__()

        blur_group = self.init_blur_section()

        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)
        self.layout.setAlignment(QtCore.Qt.AlignTop)
        # self.layout.setContentsMargins(0, 0, 0, 0)

        self.layout.addWidget(blur_group)

        self.selected_background_section()

    def init_blur_section(self) -> QtWidgets.QGroupBox:
        blur_group = QtWidgets.QGroupBox("Global")

        min_blur, max_blur = 1, 100

        blur_group.slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        blur_group.spin_box = ConfigManager.register(
            ("settings", "background", "blur_strength"),
            QtWidgets.QSpinBox(),
        )

        label = QtWidgets.QLabel("Blur Strength")

        # Setting a step between QSlider values doesn't seem to work
        blur_group.slider.valueChanged.connect(blur_group.spin_box.setValue)
        blur_group.slider.setMinimum(min_blur)
        blur_group.slider.setMaximum(max_blur)

        blur_group.spin_box.valueChanged.connect(blur_group.slider.setValue)
        blur_group.spin_box.setMinimum(min_blur)
        blur_group.spin_box.setMaximum(max_blur)

        layout = QtWidgets.QGridLayout()
        layout.addWidget(label, 1, 0)
        layout.addWidget(blur_group.slider, 1, 1)
        layout.addWidget(blur_group.spin_box, 1, 2)
        layout.setAlignment(QtCore.Qt.AlignTop)

        blur_group.setLayout(layout)

        return blur_group

    def selected_background_section(self) -> None:
        self.selected_background_groupbox = QtWidgets.QGroupBox("Select Backgrounds")

        # solid color section

        solid_color_group = ConfigManager.register(
            ("background", BackgroundType.SOLID_COLOR, "enabled"),
            QtWidgets.QCheckBox("Solid Color"),
        )

        # gradient section

        gradient_checkboxes = [
            linear_gradient_checkbox := ConfigManager.register(
                ("background", BackgroundType.LINEAR_GRADIENT, "enabled"),
                QtWidgets.QCheckBox("Linear Gradient"),
            ),
            radial_gradient_checkbox := ConfigManager.register(
                ("background", BackgroundType.RADIAL_GRADIENT, "enabled"),
                QtWidgets.QCheckBox("Radial Gradient"),
            ),
        ]

        gradient_color_groupbox = QtWidgets.QGroupBox("Gradient Color", checkable=True)
        gradient_color_groupbox.setLayout(QtWidgets.QVBoxLayout())

        def checkbox_toggle() -> None:
            gradient_color_groupbox.setChecked(
                any(cb.isChecked() for cb in gradient_checkboxes),
            )

        linear_gradient_checkbox.clicked.connect(checkbox_toggle)
        radial_gradient_checkbox.clicked.connect(checkbox_toggle)
        gradient_color_groupbox.clicked.connect(
            lambda checked: [cb.setChecked(checked) for cb in gradient_checkboxes],
        )

        gradient_color_groupbox.layout().addWidget(linear_gradient_checkbox)
        gradient_color_groupbox.layout().addWidget(radial_gradient_checkbox)

        # colored noise section

        colored_noise_groupbox = ConfigManager.register(
            ("background", BackgroundType.COLORED_NOISE, "enabled"),
            QtWidgets.QGroupBox("Colored Noise", checkable=True),
        )
        colored_noise_groupbox.setLayout(QtWidgets.QGridLayout())

        colored_noise_groupbox.slider = QtWidgets.QSlider(
            QtCore.Qt.Orientation.Horizontal,
        )
        colored_noise_groupbox.spin_box = ConfigManager.register(
            ("background", BackgroundType.COLORED_NOISE, "no_colors"),
            QtWidgets.QSpinBox(),
        )

        min_colors, max_colors = 3, 10

        colored_noise_groupbox.slider.valueChanged.connect(
            colored_noise_groupbox.spin_box.setValue,
        )
        colored_noise_groupbox.slider.setMinimum(min_colors)
        colored_noise_groupbox.slider.setMaximum(max_colors)

        colored_noise_groupbox.spin_box.valueChanged.connect(
            colored_noise_groupbox.slider.setValue,
        )
        colored_noise_groupbox.spin_box.setMinimum(min_colors)
        colored_noise_groupbox.spin_box.setMaximum(max_colors)

        colored_noise_blur_checkbox = ConfigManager.register(
            ("background", BackgroundType.COLORED_NOISE, "blur"),
            QtWidgets.QCheckBox("Blur"),
        )

        colored_noise_groupbox.layout().addWidget(colored_noise_blur_checkbox, 1, 0)
        colored_noise_groupbox.layout().addWidget(QtWidgets.QLabel("No. Colors"), 0, 0)
        colored_noise_groupbox.layout().addWidget(colored_noise_groupbox.slider, 0, 1)
        colored_noise_groupbox.layout().addWidget(colored_noise_groupbox.spin_box, 0, 2)

        # album art section

        album_art_groupbox = ConfigManager.register(
            ("background", BackgroundType.ALBUM_ART, "enabled"),
            QtWidgets.QGroupBox("Album Art", checkable=True),
        )
        album_art_groupbox.setLayout(QtWidgets.QVBoxLayout())
        album_art_groupbox.layout().addWidget(
            ConfigManager.register(
                ("background", BackgroundType.ALBUM_ART, "blur"),
                QtWidgets.QCheckBox("Blur"),
            ),
        )

        wallpaper_groupbox = ConfigManager.register(
            ("background", BackgroundType.DEFAULT_WALLPAPER, "enabled"),
            QtWidgets.QGroupBox("Wallpaper", checkable=True),
        )
        wallpaper_groupbox.setLayout(QtWidgets.QVBoxLayout())
        wallpaper_groupbox.layout().addWidget(
            ConfigManager.register(
                ("background", BackgroundType.DEFAULT_WALLPAPER, "blur"),
                QtWidgets.QCheckBox("Blur"),
            ),
        )

        groupbox_layout = QtWidgets.QVBoxLayout()
        self.selected_background_groupbox.setLayout(groupbox_layout)

        groupbox_layout.addWidget(
            QtWidgets.QLabel("All enabled backgrounds will be selected randomly"),
        )
        groupbox_layout.addWidget(solid_color_group)
        groupbox_layout.addWidget(gradient_color_groupbox)
        groupbox_layout.addWidget(colored_noise_groupbox)
        groupbox_layout.addWidget(album_art_groupbox)
        groupbox_layout.addWidget(wallpaper_groupbox)

        self.layout.addWidget(self.selected_background_groupbox)


class ForegroundTab(QtWidgets.QGroupBox):
    def __init__(self, parent: Self | None = None) -> None:
        super().__init__(parent)

        min_res, max_res = 50, 1950
        interval = 50

        self.slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.spin_box = ConfigManager.register(
            ("settings", "foreground", "size"),
            QtWidgets.QSpinBox(),
        )

        label = QtWidgets.QLabel("Size (px)")

        # Setting a step between QSlider values doesn't seem to work
        self.slider.valueChanged.connect(lambda x: self.spin_box.setValue(x * interval))
        self.slider.setMinimum(min_res // interval)
        self.slider.setMaximum(max_res // interval)

        self.spin_box.valueChanged.connect(
            lambda x: self.slider.setValue(x // interval),
        )
        self.spin_box.setMinimum(min_res)
        self.spin_box.setMaximum(max_res)
        self.spin_box.setSingleStep(interval)

        drop_shadow_checkbox = ConfigManager.register(
            ("settings", "foreground", "drop_shadow"),
            QtWidgets.QCheckBox("Drop Shadow"),
        )

        spotify_codes_checkbox = ConfigManager.register(
            ("settings", "foreground", "spotify_code"),
            QtWidgets.QCheckBox("Show Spotify Code"),
        )

        layout = QtWidgets.QGridLayout()
        layout.addWidget(label, 1, 0)
        layout.addWidget(self.slider, 1, 1)
        layout.addWidget(self.spin_box, 1, 2)
        layout.addWidget(drop_shadow_checkbox, 2, 0, 1, 3)
        layout.addWidget(spotify_codes_checkbox, 3, 0, 1, 3)
        layout.setAlignment(QtCore.Qt.AlignTop)

        self.setTitle("Show Foreground Art")
        self.setLayout(layout)
        self.setCheckable(True)

        ConfigManager.register(
            ("settings", "foreground", "enabled"),
            self,
        )


class ServiceSettings(QtWidgets.QWidget):
    def __init__(self, parent: Self | None = None) -> None:
        super().__init__(parent)

        self.main_layout = QtWidgets.QFormLayout()

        # https://stackoverflow.com/questions/11826036/pyside-show-hide-layouts

        self.api_keys_stacked = QtWidgets.QStackedWidget()

        self.service_combo = ConfigManager.register(
            ("settings", "service", "option"),
            QtWidgets.QComboBox(),
        )

        self.service_combo.addItems(["Spotify (recommended)", "Last.fm"])
        self.service_combo.currentIndexChanged.connect(
            self.api_keys_stacked.setCurrentIndex,
        )

        self.main_layout.addRow("Service", self.service_combo)
        self.main_layout.addRow(self.api_keys_stacked)

        def create_help_link(service_name: str) -> QtWidgets.QLabel:
            page = "https://github.com/jac0b-w/AlbumPaper/wiki/Getting-API-Keys"
            help_link = QtWidgets.QLabel(
                f'<a href="{page}#{service_name.replace(".", "")}">'
                f"Where do I find {service_name} API keys?</a>",
            )
            help_link.linkActivated.connect(
                lambda link: QtGui.QDesktopServices.openUrl(QtCore.QUrl(link)),
            )
            return help_link

        # spotify section
        # API Keys
        secrets_group = QtWidgets.QGroupBox("Credentials")
        secrets_layout = QtWidgets.QFormLayout()
        secrets_group.setLayout(secrets_layout)

        self.spotify_client_id = ConfigManager.register(
            ("services", "spotify", "client_id"),
            QtWidgets.QLineEdit(),
        )
        self.spotify_client_secret = ConfigManager.register(
            ("services", "spotify", "client_secret"),
            QtWidgets.QLineEdit(),
        )
        self.spotify_client_id.setPlaceholderText("Client ID")
        self.spotify_client_secret.setPlaceholderText("Client Secret")
        self.spotify_client_id.setMaxLength(32)
        self.spotify_client_secret.setMaxLength(32)
        self.spotify_specific_device_checkbox = ConfigManager.register(
            ("settings", "service", "is_device_specific"),
            QtWidgets.QComboBox(),
        )
        self.spotify_specific_device_checkbox.addItems(
            ["All Devices", "Only this Device (Spotify Desktop)"],
        )

        widget = QtWidgets.QWidget()
        self.api_keys_stacked.addWidget(widget)
        layout = QtWidgets.QFormLayout()
        widget.setLayout(layout)
        secrets_layout.addRow("Client ID", self.spotify_client_id)
        secrets_layout.addRow("Client Secret", self.spotify_client_secret)
        secrets_layout.addRow(create_help_link("Spotify"))
        layout.addRow(secrets_group)
        layout.addRow("Sync from", self.spotify_specific_device_checkbox)

        # last.fm section
        # Username/API Keys
        secrets_group = QtWidgets.QGroupBox("Credentials")
        secrets_layout = QtWidgets.QFormLayout()
        secrets_group.setLayout(secrets_layout)

        self.lastfm_username = ConfigManager.register(
            ("services", "last.fm", "username"),
            QtWidgets.QLineEdit(),
        )
        self.lastfm_api_key = ConfigManager.register(
            ("services", "last.fm", "api_key"),
            QtWidgets.QLineEdit(),
        )
        self.lastfm_username.setPlaceholderText("Username")
        self.lastfm_api_key.setPlaceholderText("API Key")
        self.lastfm_api_key.setMaxLength(32)

        widget = QtWidgets.QWidget()
        self.api_keys_stacked.addWidget(widget)
        layout = QtWidgets.QFormLayout()
        widget.setLayout(layout)
        secrets_layout.addRow("Username", self.lastfm_username)
        secrets_layout.addRow("API Key", self.lastfm_api_key)
        secrets_layout.addRow(create_help_link("Last.fm"))

        layout.addRow(secrets_group)

        self.setLayout(self.main_layout)


class Sidebar(QtWidgets.QLabel):
    def __init__(self, parent: Self | None = None) -> None:
        super().__init__(parent)

        self.setStyleSheet("background-color: rgba(128, 128, 128, 30);")
        self.setFixedWidth(150)

        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().setAlignment(Qt.AlignTop)
        self.layout().setContentsMargins(0, 0, 0, 0)

        self.general_button = SidebarButton("General")
        self.layout().addWidget(self.general_button)
        self.general_button.clicked.connect(
            lambda: parent.settings_pages.setCurrentIndex(0),
        )

        self.wallpaper_button = SidebarButton("Wallpaper")
        self.layout().addWidget(self.wallpaper_button)
        self.wallpaper_button.clicked.connect(
            lambda: parent.settings_pages.setCurrentIndex(1),
        )

        self.service_button = SidebarButton("Service")
        self.layout().addWidget(self.service_button)
        self.service_button.clicked.connect(
            lambda: parent.settings_pages.setCurrentIndex(2),
        )


class SidebarButton(QtWidgets.QPushButton):
    def __init__(self, text: str, parent: Self | None = None) -> None:
        super().__init__(text, parent)
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                padding: 8px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 30);
            }
        """)
