import sys
from pathlib import Path

import configobj
import configobj.validate
from PySide6 import QtWidgets


class AppPaths:
    PROJECT_ROOT = Path(sys.argv[0]).resolve().parent

    DEFAULT_WALLPAPER = PROJECT_ROOT / "./cache/images/default_wallpaper.jpg"
    GENERATED_WALLPAPER = PROJECT_ROOT / "./cache/images/generated_wallpaper.png"
    DROP_SHADOW = PROJECT_ROOT / "./cache/images/drop_shadow.png"

    CONFIG_DIR = PROJECT_ROOT / "./config/"
    DEV_CONFIG_DIR = PROJECT_ROOT / "./config-dev/"

    SECRETS = "secrets.ini"
    GLOBAL = "global.ini"
    BACKGROUND = "background.ini"

    @classmethod
    def get_config(cls, file: Path | str) -> str:
        dev_dir = cls.PROJECT_ROOT / cls.DEV_CONFIG_DIR
        if dev_dir.is_dir():
            path = dev_dir / file
        else:
            path = cls.PROJECT_ROOT / cls.CONFIG_DIR / file

        return str(path.absolute())

    @classmethod
    def get_spec(cls, file: Path | str) -> str:
        dev_dir = cls.PROJECT_ROOT / cls.DEV_CONFIG_DIR
        if dev_dir.is_dir():
            path = dev_dir / "spec" / file
        else:
            path = cls.PROJECT_ROOT / cls.CONFIG_DIR / "spec" / file

        return str(path.absolute())


class ConfigManager:
    services = configobj.ConfigObj(AppPaths.get_config(AppPaths.SECRETS))

    _validator = configobj.validate.Validator()

    settings = configobj.ConfigObj(
        AppPaths.get_config(AppPaths.GLOBAL),
        configspec=AppPaths.get_spec(AppPaths.GLOBAL),
    )
    settings.validate(_validator)

    background = configobj.ConfigObj(
        AppPaths.get_config(AppPaths.BACKGROUND),
        configspec=AppPaths.get_spec(AppPaths.BACKGROUND),
    )
    background.validate(_validator)

    _widgets: dict[tuple[str, ...], QtWidgets.QWidget] = {}  # noqa: RUF012

    @classmethod
    def validate_service(cls) -> bool | str:

        api_key_length = 32

        service_option = cls.value_from_key("settings", "service", "option")
        # spotify
        if service_option == 0:
            for key in ["client_id", "client_secret"]:
                if (
                    len(cls.value_from_key("services", "spotify", key))
                    != api_key_length
                ):
                    return "Set valid Spotify API keys"

        # last.fm
        elif service_option == 1:
            if not (
                2 <= len(cls.value_from_key("services", "last.fm", "username")) <= 15  # noqa: PLR2004
            ):
                return "Set valid Last.fm username"

            if (
                len(cls.value_from_key("services", "last.fm", "api_key"))
                != api_key_length
            ):
                return "Set valid Last.fm API key"

        else:
            return "Set a valid service"

        return ""

    @classmethod
    def value_from_key(cls, *keys: tuple[str, str, str]) -> bool | int | str:
        return cls.get_widget_state(cls._widgets[keys])

    @classmethod
    def save_widget_state(cls) -> None:
        cls.update_settings()
        cls.save_internal_state()

    @classmethod
    def save_internal_state(cls) -> None:
        cls.settings.write()
        cls.services.write()
        cls.background.write()

    @classmethod
    def register(cls, key: tuple[str], widget: QtWidgets.QWidget) -> QtWidgets.QWidget:
        cls._widgets[key] = widget
        return widget

    @classmethod
    def get_widget_state(cls, widget: QtWidgets.QWidget) -> bool | int | str:
        if isinstance(widget, (QtWidgets.QCheckBox, QtWidgets.QGroupBox)):
            return widget.isChecked()

        if isinstance(widget, QtWidgets.QSpinBox):
            return widget.value()

        if isinstance(widget, QtWidgets.QLineEdit):
            return widget.text()

        if isinstance(widget, QtWidgets.QComboBox):
            return widget.currentIndex()

        msg = "Unknown Widget Type"
        raise ValueError(msg)

    @classmethod
    def set_widget_state(
        cls,
        widget: QtWidgets.QWidget,
        *,
        value: bool | int | str,
    ) -> None:
        if isinstance(widget, (QtWidgets.QCheckBox, QtWidgets.QGroupBox)):
            widget.setChecked(value)

        if isinstance(widget, QtWidgets.QSpinBox):
            widget.setValue(value)

        if isinstance(widget, QtWidgets.QLineEdit):
            widget.setText(value)

        if isinstance(widget, QtWidgets.QComboBox):
            widget.setCurrentIndex(value)

    @classmethod
    def update_settings(cls) -> None:
        for key, widget in cls._widgets.items():
            if key[0] == "settings":
                file = cls.settings

            if key[0] == "services":
                file = cls.services

            if key[0] == "background":
                file = cls.background

            file[key[1]][key[2]] = cls.get_widget_state(widget)

    @classmethod
    def init_widgets(cls) -> None:
        for key, widget in cls._widgets.items():
            if key[0] == "settings":
                file = cls.settings

            if key[0] == "services":
                file = cls.services

            if key[0] == "background":
                file = cls.background

            cls.set_widget_state(widget, value=file[key[1]][key[2]])
