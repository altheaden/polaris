import os
import shutil

import parsl
from parsl.config import Config
from parsl.executors import HighThroughputExecutor
from parsl.launchers import SimpleLauncher
from parsl.providers import LocalProvider


def parsl_setup(local=False):
    parsl.clear()

    if local:
        parsl.load()
        return

    executor = _create_executor()
    return parsl.load(executor)  # returns Parsl data flow kernel


def make_output_dir():
    out_dir = os.path.join(os.getcwd(), 'outputs')
    try:
        os.makedirs(out_dir)
    except FileExistsError:
        shutil.rmtree(out_dir)
        os.makedirs(out_dir)

    return out_dir


def _create_executor(nodes=1):
    """
    Create a Parsl executor
    """
    config = Config(
        executors=[
            HighThroughputExecutor(
                label='Polaris_HTEX',
                provider=LocalProvider(
                    launcher=SimpleLauncher(),
                    nodes_per_block=nodes,
                    init_blocks=1,
                    max_blocks=1,
                    cmd_timeout=120,
                )
            )
        ]
    )
    return config
