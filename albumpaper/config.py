import ast, configobj, validate

class ConfigValidationError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message


class ConfigManager:
    _settings_path = "settings.ini"
    _services_path = "services.ini"
    _validator = validate.Validator()
    
    settings = configobj.ConfigObj(_settings_path, configspec = "configspec.ini")
    settings.validate(_validator)
    services = configobj.ConfigObj(_services_path)

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
        
        cls.settings.write()
        cls.services.write()

    @classmethod
    def theme(cls) -> dict:
        theme_name = cls.settings["theme"]["name"]
        try:
            with open(f"themes/{theme_name}.py") as f:
                return ast.literal_eval(f.read())
        except FileNotFoundError:
            return {}
