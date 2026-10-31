from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ELEVANT_")

    env: Literal["local", "staging", "production"] = "local"
    doubles: bool = False
    foundry_project_endpoint: str = Field("", validation_alias="FOUNDRY_PROJECT_ENDPOINT")
    docintel_endpoint: str = Field("", validation_alias="DOCINTEL_ENDPOINT")
    model: str = "gpt-5-mini"
    cosmos_endpoint: str = "http://localhost:8081"
    blob_endpoint: str = ""
    database: str = "elevant"
    image: str = "local"
    appinsights: str = Field("", validation_alias="APPLICATIONINSIGHTS_CONNECTION_STRING")

    @model_validator(mode="after")
    def no_doubles_in_production(self) -> Self:
        if self.doubles and self.env == "production":
            raise ValueError("ELEVANT_DOUBLES is refused when ELEVANT_ENV is production")
        return self
