from pydantic import BaseSettings


class BaseConfig(BaseSettings.Config):
    @classmethod
    def prepare_field(cls, field) -> None:
        if "env_names" in field.field_info.extra:
            return
        return super().prepare_field(field)


class ScrapperSettings(BaseSettings):
    headless: bool = True

    class Config(BaseConfig):
        env_prefix = "SCRAPER_"


class ModelsSettings(BaseSettings):
    adult_image_path: str = None
    phishing_image_path: str = None
    phishing_code_path: str = None
    phishing_text_path: str = None
    phishing_url_path: str = None
    phishing_model_path: str = None
    phishing_url_threshold: float = 0.5

    class Config(BaseConfig):
        env_prefix = "MODEL_"


class Settings(ScrapperSettings, ModelsSettings):
    class Config(BaseConfig):
        env_prefix = ""
        env_file = ".env"
