import os
from pathlib import Path

from celery.signals import heartbeat_sent, worker_ready, worker_shutdown

from maxkb.conf import PROJECT_DIR


def get_worker_signal_dir():
    signal_dir = os.getenv("MAXKB_TMP_DIR") or os.getenv("TMPDIR") or os.path.join(PROJECT_DIR, ".local", "maxkb", "tmp")
    path = Path(signal_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


@heartbeat_sent.connect
def heartbeat(sender, **kwargs):
    worker_name = sender.eventer.hostname.split('@')[0]
    heartbeat_path = get_worker_signal_dir() / 'worker_heartbeat_{}'.format(worker_name)
    heartbeat_path.touch()


@worker_ready.connect
def worker_ready(sender, **kwargs):
    worker_name = sender.hostname.split('@')[0]
    ready_path = get_worker_signal_dir() / 'worker_ready_{}'.format(worker_name)
    ready_path.touch()


@worker_shutdown.connect
def worker_shutdown(sender, **kwargs):
    worker_name = sender.hostname.split('@')[0]
    for signal in ['ready', 'heartbeat']:
        path = get_worker_signal_dir() / 'worker_{}_{}'.format(signal, worker_name)
        path.unlink(missing_ok=True)
