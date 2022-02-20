import os
import signal
from datetime import datetime


def ENV(key, to=lambda v: v):
    value = os.environ.get(key)
    if value is None:
        fail(f'Environment variable {key} is not set')
    return to(value)


def fail(message):
    output = f'ERROR: {message}'
    log_path = os.environ.get('ERROR_LOG_PATH')
    if log_path is not None:
        with open(log_path, 'a') as file:
            file.write(f'{datetime.now()}: {output}\n')
    print(output)
    kill_process()


def kill_process():
    os.kill(os.getpid(), signal.SIGINT)
