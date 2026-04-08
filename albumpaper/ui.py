from pathlib import Path
from typing import TYPE_CHECKING, Self

from configuration import ConfigManager, ConfigValidationError
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from wallpaper import Wallpaper

if TYPE_CHECKING:
    from collections.abc import Callable


class SystemTrayIcon(QtWidgets.QSystemTrayIcon):
    def __init__(
        self,
        icon: QtGui.QIcon,
        parent: QtWidgets.QWidget,
        signal: QtCore.Signal,
        version: str,
        pause_state_manager,
    ) -> None:
        super().__init__(icon, parent)
        self.setToolTip("AlbumPaper")
        self.context_menu = QtWidgets.QMenu(parent)
        self.signal = signal
        self.VERSION = version
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

        # self.context_menu.addSeparator()

        # self.help_menu = self.context_menu.addMenu(
        #     QtGui.QIcon(f"assets/icons/{self.icon_color}/help.png"), "Help"
        # )
        # help_latest = self.help_menu.addAction("Latest Release")
        # help_current = self.help_menu.addAction("This Release")
        # github_link = "https://github.com/jac0b-w/AlbumPaper/"
        # help_latest.triggered.connect(
        #     self.open_link(f"{github_link}blob/master/README.md")
        # )
        # help_current.triggered.connect(
        #     self.open_link(f"{github_link}blob/{self.VERSION}/README.md")
        # )

        # bug_report_item = self.context_menu.addAction(
        #     QtGui.QIcon(f"assets/icons/{self.icon_color}/bug_report.png"), "Bug Report"
        # )
        # bug_report_item.triggered.connect(self.open_link(f"{github_link}issues"))

        # release_item = self.context_menu.addAction(
        #     QtGui.QIcon(f"assets/icons/{self.icon_color}/update.png"), f"{self.VERSION}"
        # )
        # release_item.triggered.connect(self.open_link(f"{github_link}releases"))

        self.context_menu.addSeparator()

        self.pause_item = self.context_menu.addAction(
            QtGui.QIcon(f"assets/icons/{self.icon_color}/pause.png"), "Pause"
        )
        self.pause_item.triggered.connect(self.toggle_pause)

        restart_item = self.context_menu.addAction(
            QtGui.QIcon(f"assets/icons/{self.icon_color}/restart.png"), "Restart"
        )
        restart_item.triggered.connect(self.exit(1))

        exit_item = self.context_menu.addAction(
            QtGui.QIcon(f"assets/icons/{self.icon_color}/close.png"), "Quit"
        )
        exit_item.triggered.connect(self.exit(0))

        self.setContextMenu(self.context_menu)
        self.activated.connect(self.clicked)

        self.messageClicked.connect(
            self.open_link("https://github.com/jac0b-w/AlbumPaper/releases")
        )

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
            QtGui.QIcon(f"assets/icons/{self.icon_color}/{options['icon']}.png")
        )
        self.pause_item.setEnabled(options["enabled"])

        self.setIcon(QtGui.QIcon(f"assets/icons/{state}.png"))

    def set_default_wallpaper(self) -> None:
        Wallpaper.set_default()
        self.showMessage("Saved", "Wallpaper saved as default")

    def open_link(self, link: str) -> Callable:
        return lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl(link))

    def exit(self, exit_code: int) -> Callable:
        def exit_function() -> None:
            Wallpaper.set(is_default=True)
            QtWidgets.QApplication.exit(exit_code)

        return exit_function

    def update_value(self, value: int):
        self.slider.setValue(value)
        self.spin_box.setValue(value)


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
            self.setWindowIcon(QtGui.QIcon(settings_icon_path))

        # self.init_service_section()
        # self.main_layout.addRow(QtWidgets.QLabel(""))
        # self.init_layer_section()
        # self.main_layout.addRow(QtWidgets.QLabel(""))
        # self.init_misc_section()
        # self.main_layout.addRow(QtWidgets.QLabel(""))

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

        # Save button
        # self.save_button = QtWidgets.QPushButton("Save")
        # self.save_button.clicked.connect(self.save)
        # self.save_button.setDefault(True)
        # self.main_layout.addRow("", self.save_button)

        self.setLayout(self.main_layout)

        ConfigManager.init_widgets()

    def closeEvent(self, event):
        self.save()
        # return super().closeEvent(event)

    def save(self):
        try:
            ConfigManager.save()  # save settings.ini and services.ini
        except ConfigValidationError as e:
            print("ERROR")
            self.tray_icon.showMessage(e.message, "")
        else:
            QtWidgets.QApplication.exit(1)  # send restart exit code


class GeneralSettings(QtWidgets.QWidget):
    def __init__(self, parent: Self | None = None) -> None:
        super().__init__(parent)

        self.main_layout = QtWidgets.QFormLayout()

        self.default_wallpaper_widget = DefaultWallpaperPreview(self)

        self.main_layout.addRow("Default Wallpaper", self.default_wallpaper_widget)

        self.check_updates_checkbox = ConfigManager.register(
            ("settings", "updates", "check_for_updates"),
            QtWidgets.QCheckBox(),
        )
        self.main_layout.addRow("Check for updates", self.check_updates_checkbox)

        self.battery_saver_checkbox = ConfigManager.register(
            ("settings", "power", "disable_on_battery_saver"),
            QtWidgets.QCheckBox(),
        )
        self.main_layout.addRow("Pause on Battery Saver", self.battery_saver_checkbox)

        self.setLayout(self.main_layout)


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
            f"background-color: rgba({color.red()}, {color.green()}, {color.blue()}, 255);"
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
        self.pixmap = QtGui.QPixmap("images/default_wallpaper.jpg").scaledToWidth(
            w, Qt.SmoothTransformation
        )
        self.label.setPixmap(self.pixmap)

    def set_default_wallpaper(self) -> None:
        Wallpaper.set_default()
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
            ("background", "solidcolor", "enabled"),
            QtWidgets.QCheckBox("Solid Color"),
        )

        # gradient section

        gradient_checkboxes = [
            linear_gradient_checkbox := ConfigManager.register(
                ("background", "lineargradient", "enabled"),
                QtWidgets.QCheckBox("Linear Gradient"),
            ),
            radial_gradient_checkbox := ConfigManager.register(
                ("background", "radialgradient", "enabled"),
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
            lambda checked: [
                cb.setChecked(checked) for cb in gradient_checkboxes
            ],
        )

        gradient_color_groupbox.layout().addWidget(linear_gradient_checkbox)
        gradient_color_groupbox.layout().addWidget(radial_gradient_checkbox)

        # colored noise section

        colored_noise_groupbox = ConfigManager.register(
            ("background", "colorednoise", "enabled"),
            QtWidgets.QGroupBox("Colored Noise", checkable=True),
        )
        colored_noise_groupbox.setLayout(QtWidgets.QGridLayout())

        colored_noise_groupbox.slider = QtWidgets.QSlider(
            QtCore.Qt.Orientation.Horizontal,
        )
        colored_noise_groupbox.spin_box = ConfigManager.register(
            ("background", "colorednoise", "no_colors"),
            QtWidgets.QSpinBox(),
        )

        min_colors, max_colors = 3, 10

        colored_noise_groupbox.slider.valueChanged.connect(
            colored_noise_groupbox.spin_box.setValue
        )
        colored_noise_groupbox.slider.setMinimum(min_colors)
        colored_noise_groupbox.slider.setMaximum(max_colors)

        colored_noise_groupbox.spin_box.valueChanged.connect(
            colored_noise_groupbox.slider.setValue
        )
        colored_noise_groupbox.spin_box.setMinimum(min_colors)
        colored_noise_groupbox.spin_box.setMaximum(max_colors)

        colored_noise_blur_checkbox = ConfigManager.register(
            ("background", "colorednoise", "blur"),
            QtWidgets.QCheckBox("Blur"),
        )

        colored_noise_groupbox.layout().addWidget(colored_noise_blur_checkbox, 1, 0)
        colored_noise_groupbox.layout().addWidget(QtWidgets.QLabel("No. Colors"), 0, 0)
        colored_noise_groupbox.layout().addWidget(colored_noise_groupbox.slider, 0, 1)
        colored_noise_groupbox.layout().addWidget(colored_noise_groupbox.spin_box, 0, 2)

        # album art section

        album_art_groupbox = ConfigManager.register(
            ("background", "albumart", "enabled"),
            QtWidgets.QGroupBox("Album Art", checkable=True),
        )
        album_art_groupbox.setLayout(QtWidgets.QVBoxLayout())
        album_art_groupbox.layout().addWidget(
            ConfigManager.register(
                ("background", "albumart", "blur"),
                QtWidgets.QCheckBox("Blur"),
            ),
        )

        wallpaper_groupbox = ConfigManager.register(
            ("background", "wallpaper", "enabled"),
            QtWidgets.QGroupBox("Wallpaper", checkable=True),
        )
        wallpaper_groupbox.setLayout(QtWidgets.QVBoxLayout())
        wallpaper_groupbox.layout().addWidget(ConfigManager.register(
                ("background", "wallpaper", "blur"),
                QtWidgets.QCheckBox("Blur"),
            ))

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
            ("settings","foreground","size"),
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

        layout = QtWidgets.QGridLayout()
        layout.addWidget(label, 1, 0)
        layout.addWidget(self.slider, 1, 1)
        layout.addWidget(self.spin_box, 1, 2)
        layout.setAlignment(QtCore.Qt.AlignTop)

        self.setTitle("Show Foreground Art")
        self.setLayout(layout)
        self.setCheckable(True)

        ConfigManager.register(
            ("settings","foreground","enabled"),
            self,
        )


class ServiceSettings(QtWidgets.QWidget):
    def __init__(self, parent: Self | None = None) -> None:
        super().__init__(parent)

        self.main_layout = QtWidgets.QFormLayout()

        # https://stackoverflow.com/questions/11826036/pyside-show-hide-layouts

        index = {"spotify": 0, "last.fm": 1}[ConfigManager.settings["service"]["name"]]

        self.api_keys_stacked = QtWidgets.QStackedWidget()
        self.api_keys_stacked.setCurrentIndex(index)

        self.service_combo = QtWidgets.QComboBox()
        self.service_combo.addItems(["Spotify (recommended)", "Last.fm"])
        self.service_combo.currentIndexChanged.connect(
            self.api_keys_stacked.setCurrentIndex,
        )

        self.main_layout.addRow("Service", self.service_combo)
        self.main_layout.addRow(self.api_keys_stacked)

        def create_help_link(service_name: str) -> QtWidgets.QLabel:
            help_link = QtWidgets.QLabel(
                f'<a href="https://github.com/jac0b-w/AlbumPaper/wiki/Getting-API-Keys#{service_name.replace(".", "")}">'
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
        self.spotify_specific_device_checkbox = QtWidgets.QComboBox()
        self.spotify_specific_device_checkbox.addItems(
            ["All Devices", "Only this Device (Spotify Desktop)"]
        )
        self.spotify_specific_device_checkbox.setCurrentIndex(
            int(ConfigManager.settings["service"]["is_device_specific"])
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
