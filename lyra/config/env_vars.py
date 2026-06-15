from types import SimpleNamespace
from lyra.util.dirs import load_config

CONFIG_PATH = "~/.config/lyra/config.json"
config = load_config(CONFIG_PATH)

env_vars = SimpleNamespace(
    host=config["host"],
    api_port=config["apiPort"],
    mode=config["mode"],
    verbose=config["verbose"] == "1",
)
