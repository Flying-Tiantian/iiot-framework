import socket
from params import params

SELF_ADDR = socket.gethostbyname(socket.gethostname())

CONFIG_BROKER = {
    'listeners': {
        'default': {
            'bind': '127.0.0.1' + ':' + str(params.broker_port),
            'type': 'tcp',
            'max-connections': 0
        },
        'tcp-ssl': {
            'bind': SELF_ADDR + ':' + str(params.broker_port),
            'type': 'tcp',
            'max-connections': 0,
            'ssl': 'off',
            'cafile': None,
            'capath': None,
            'cadata': None,
            'certfile': None,
            'keyfile': None
        }
    },
    'timeout-disconnect-delay': 2,
    'auth': {
        'plugins': ['auth_anonymous', 'auth_file'],
        'allow-anonymous': False,
        'password-file': 'path/to/password/file',
        'name-as-password': params.test_mode
    },
    'topic-check': {
        'enabled': True,
        'plugins': ['topic_filter']
    }
}

CONFIG_CLIENT = {
    'keep_alive': 10,
    'ping_delay': 1,
    'default_qos': 2,
    'default_retain': False,
    'auto_reconnect': True,
    'reconnect_max_interval': 5,
    'reconnect_retries': 10,
    'broker': {
        'uri': 'mqtt://' + params.device_ID + ':' + params.device_ID + '@' + str(params.broker_address),
        'cafile': None,
        'capath': None,
        'cadata': None
    }
}

print(CONFIG_CLIENT)
