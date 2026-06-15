from json import load
from shutil import copy2
from os import path, makedirs
from importlib.resources import files

TEMPLATE_FILE = files("lyra.templates").joinpath("config.json")


def load_config(config_path: str):
    """Carga los datos del archivo de configuración desde ./config/lyra/config.json o crea un archivo template

    Args:
        config_path (str): Ruta al archivo de configuración

    Returns:
        json: Regresa la información del archivo de configuración en memoria
    """
    config_path = path.expanduser(config_path)
    path_exists = path.exists(config_path)

    if not path_exists:
        makedirs(path.dirname(config_path), exist_ok=True)
        copy2(TEMPLATE_FILE, config_path)

        raise FileNotFoundError(
            f"Configuration files wasn't found at {config_path} adding a template"
        )

    with open(config_path, "r") as config_file:
        return load(config_file)
