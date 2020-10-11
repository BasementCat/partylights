import os
import json

import yaml


def _load_config_file(filename=None):
    if not filename:
        filename = os.path.join('.', 'config', 'main.yaml')
    filename = os.path.expanduser(filename)
    if not os.path.exists(filename):
        raise RuntimeError(f"Config file {filename} does not exist")
    with open(filename, 'r') as fp:
        if filename.lower().endswith('.yml') or filename.lower().endswith('.yaml'):
            return filename, yaml.load(fp)
        elif filename.lower().endswith('.json'):
            return filename, json.load(fp)
        else:
            raise RuntimeError(f"Config file {filename} is not of a supported type (YAML or JSON)")


def load_config(filename=None):
    filename, config = _load_config_file(filename=filename)
    if isinstance(config, dict):
        for k, v in list(config.items()):
            if isinstance(v, str) and v.startswith('@'):
                config[k] = load_config(filename=os.path.join(os.path.dirname(filename), v[1:]))
    return config
