import os
from datetime import timedelta

config = {
    'engine': 'postgresql://localhost/jupyter-flashcard',
    'host': 'localhost',
    'port': 7000,
    'debug': False,
    'threaded': False,
    'srs': {
        1: timedelta(minutes=10),
        2: timedelta(hours=4),
        3: timedelta(hours=8),
        4: timedelta(days=1),
        5: timedelta(days=3),
        6: timedelta(days=7),
        7: timedelta(weeks=2),
        8: timedelta(weeks=4),
        9: timedelta(weeks=16)
    }
}


for k, v in config.items():
    env_k = 'JF_' + k.upper()
    if env_k in os.environ.keys():
        env_v = os.environ[env_k]

        if type(v) == 'int':
            config[k] = int(env_v)
        elif type(v) == 'bool':
            config[k] = bool(env_v)
        elif type(v) == 'str':
            config[k] = env_v
