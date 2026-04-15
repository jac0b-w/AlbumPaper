from pathlib import Path

import configobj
import configobj.validate
from PySide6 import QtWidgets


class AppPaths:
    DEFAULT_WALLPAPER = "./cache/images/default_wallpaper.jpg"
    GENERATED_WALLPAPER = "./cache/images/generated_wallpaper.png"
    DROP_SHADOW = "./cache/images/drop_shadow.png"

    DEV_SERVICES_SECRETS = "./config/secrets/services-dev.ini"
    SERVICES_SECRETS = "./config/secrets/services.ini"

    GLOBAL_SETTINGS = "./config/global.ini"
    GLOBAL_SETTINGS_SPEC = "./config/spec/global.ini"

    BACKGROUND_SETTINGS = "./config/background.ini"
    BACKGROUND_SETTINGS_SPEC = "./config/spec/background.ini"


class ConfigManager:
    dev_services_file = Path(AppPaths.DEV_SERVICES_SECRETS)
    if dev_services_file.is_file():
        print("Using developer API keys")
        services = configobj.ConfigObj(AppPaths.DEV_SERVICES_SECRETS)
    else:
        services = configobj.ConfigObj(AppPaths.SERVICES_SECRETS)

    _validator = configobj.validate.Validator()

    settings = configobj.ConfigObj(
        AppPaths.GLOBAL_SETTINGS,
        configspec=AppPaths.GLOBAL_SETTINGS_SPEC,
    )
    settings.validate(_validator)

    background = configobj.ConfigObj(
        AppPaths.BACKGROUND_SETTINGS,
        configspec=AppPaths.BACKGROUND_SETTINGS_SPEC,
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
