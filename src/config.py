import os
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field


class AppConfigSection(BaseModel):
    mode: Literal["all", "extract", "sync"] = "all"
    delay: float = Field(default=1.0, ge=0)
    test: bool = False

class PathsConfigSection(BaseModel):
    input_dir: str = "input"
    output_csv: str = "output/transactions.csv"
    quarantine_dir: str = "output/quarantine"


class LLMConfigSection(BaseModel):
    model: str = "qwen/qwen3.5-flash-02-23"
    max_tokens_vision: int = 1000
    max_tokens_text: int = 200
    temperature: float = 0.0

class GoogleSheetsConfigSection(BaseModel):
    sync_enabled: bool = True
    sync_mode: Literal["send", "dry-run", "confirm"] = "send"
    sync_limit: Optional[int] = None
    spreadsheet_id: str = "1edxyVxRjEtYAWVETnV7398yXxCOCs9pyuhJhcuaU3xU"
    sheet_name: str = "⚪ CTO"
    service_account_path: str = "~/.config/clef_google/service-account.json"

class RootConfig(BaseModel):
    app: AppConfigSection = AppConfigSection()
    paths: PathsConfigSection = PathsConfigSection()
    llm: LLMConfigSection = LLMConfigSection()
    google_sheets: GoogleSheetsConfigSection = GoogleSheetsConfigSection()

    openrouter_api_key: str = Field(default="", exclude=True)

    def __str__(self) -> str:
        # Mask API key in string representation just in case
        rep = super().__str__()
        if self.openrouter_api_key:
            rep = rep.replace(self.openrouter_api_key, "***")
        return rep


def _resolve_path(path_value: str, project_root: Path) -> Path:
    candidate = Path(path_value).expanduser()
    if candidate.is_absolute():
        return candidate
    return project_root / candidate


def _check_no_secrets_in_yaml(yaml_data: dict) -> None:
    forbidden_keys = {"llm_keys", "api_key", "openrouter_api_key"}
    def _search_dict(d: dict):
        for k, v in d.items():
            if str(k).lower() in forbidden_keys:
                raise ValueError(f"CRITICAL SECURITY: Secret keys like '{k}' are forbidden in CONFIG.yaml.")
            if isinstance(v, dict):
                _search_dict(v)
    _search_dict(yaml_data)

def load_configuration(cli_args: dict | None = None, config_file: str = "CONFIG.yaml") -> RootConfig:
    cli_args = cli_args or {}
    project_root = Path(__file__).resolve().parent.parent
    config_path = project_root / config_file

    raw_config = {}

    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                yaml_data = yaml.safe_load(f) or {}
                _check_no_secrets_in_yaml(yaml_data)
                
                # Merge nested dictionaries
                if "app" in yaml_data:
                    raw_config.setdefault("app", {}).update(yaml_data["app"])
                if "paths" in yaml_data:
                    raw_config.setdefault("paths", {}).update(yaml_data["paths"])
                if "llm" in yaml_data:
                    raw_config.setdefault("llm", {}).update(yaml_data["llm"])
                if "google_sheets" in yaml_data:
                    raw_config.setdefault("google_sheets", {}).update(yaml_data["google_sheets"])
                
        except (OSError, ValueError, TypeError, yaml.YAMLError) as e:
            import sys
            print(f"Error reading {config_file}: {e}")
            sys.exit(2)
            
    config = RootConfig(**raw_config)

    api_key_env = os.environ.get("OPENROUTER_API_KEY", "")
    if api_key_env:
        config.openrouter_api_key = api_key_env

    # CLI Arguments overrides
    if cli_args.get("mode"):
        config.app.mode = cli_args["mode"]
    if cli_args.get("delay") is not None:
        config.app.delay = cli_args["delay"]
    if cli_args.get("test"):
        config.app.test = True
        
    if cli_args.get("input_dir") and cli_args["input_dir"] != "input":
        config.paths.input_dir = cli_args["input_dir"]
    if cli_args.get("output") and cli_args["output"] != "output/transactions.csv":
        config.paths.output_csv = cli_args["output"]
        
    # bool flags
    if "sync" in cli_args:
        config.google_sheets.sync_enabled = cli_args["sync"]
    
    if cli_args.get("sync_mode") and cli_args["sync_mode"] != "send":
        config.google_sheets.sync_mode = cli_args["sync_mode"]
    if cli_args.get("sync_limit") is not None:
        config.google_sheets.sync_limit = cli_args["sync_limit"]

    return config

def resolve_path_str(path_value: str) -> Path:
    return _resolve_path(path_value, Path(__file__).resolve().parent.parent)

