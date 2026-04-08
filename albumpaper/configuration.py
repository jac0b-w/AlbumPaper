from numpy import isin
import ast, configobj, validate
from pathlib import Path
from PySide6 import QtWidgets


class ConfigValidationError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message


class ConfigManager:
    _settings_path = "config/global.ini"

    # use developer API keys if the file exists
    _dev_services_path = "config/secrets/services-dev.ini"
    _services_path = "config/secrets/services.ini"

    _validator = validate.Validator()

    dev_services_file = Path(_dev_services_path)
    if dev_services_file.is_file():
        print("Using developer API keys")
        services = configobj.ConfigObj(_dev_services_path)
    else:
        services = configobj.ConfigObj(_services_path)

    settings = configobj.ConfigObj(_settings_path, configspec="config/spec/global.ini")
    settings.validate(_validator)

    background = configobj.ConfigObj(
        "config/background.ini", configspec="config/spec/background.ini",
    )
    background.validate(_validator)

    _widgets: dict[tuple[str, ...], QtWidgets.QWidget] = {}

    @classmethod
    def validate_service(cls):
        if cls.settings["service"]["name"] == "spotify":
            for key in ["client_id", "client_secret"]:
                try:
                    cls._validator.check(
                        "string(min=32, max=32)",
                        cls.services["spotify"][key],
                    )
                except validate.ValidateError:
                    raise ConfigValidationError("Set valid Spotify API keys")

        elif cls.settings["service"]["name"] == "last.fm":
            try:
                cls._validator.check(
                    "string(min=32, max=32)",
                    cls.services["last.fm"]["api_key"],
                )
                cls._validator.check(
                    "string(min=2, max=15)",
                    cls.services["last.fm"]["username"],
                )
            except validate.ValidateError:
                raise ConfigValidationError("Set valid Last.fm API key and username")

        else:
            raise ConfigValidationError("Set a valid service")

    @classmethod
    def save(cls) -> None:
        cls.validate_service()

        cls.update_settings()

        cls.settings.write()
        cls.services.write()
        cls.background.write()

    @classmethod
    def register(cls, key: tuple[str], widget: QtWidgets.QWidget):
        cls._widgets[key] = widget
        return widget

    @classmethod
    def get_widget_state(cls, widget: QtWidgets.QWidget):
        if isinstance(widget, (QtWidgets.QCheckBox, QtWidgets.QGroupBox)):
            return widget.isChecked()

        if isinstance(widget, QtWidgets.QSpinBox):
            return widget.value()

        if isinstance(widget, QtWidgets.QLineEdit):
            return widget.text()

        if isinstance(widget, QtWidgets.QComboBox):
            return widget.currentIndex()

        raise ValueError("Unknown Widget Type")

    @classmethod
    def set_widget_state(cls, widget: QtWidgets.QWidget, value) -> None:
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

            cls.set_widget_state(widget, file[key[1]][key[2]])
