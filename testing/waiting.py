import os
import random

# from testing import make_output_dir, parsl_setup  # debug: broken on chrys?
from __init__ import make_output_dir, parsl_setup
from parsl import bash_app
from parsl.data_provider.files import File


def main():
    """
    We have groups of filenames for files we wish to create.
    Some of these filenames depend on each other.
    """
    dfk = parsl_setup()
    out_dir = make_output_dir()

    num_total_files = 10

    futures = list()

    # create a chain of 1, 2, or 3 files that have a dependent relationship
    for i in range(num_total_files):
        num_in_chain = random.randint(1, 3)
        for j in range(num_in_chain):
            file = File(os.path.join(out_dir, f'{i}_part_{j+1}.txt'))
            futures.append(_make_file(outputs=[file], ID=f'{i}, {j+1}'))

    # create a file that depends on all output files to execute
    inputs = list()
    for future in futures:
        inputs.extend(future.outputs)
    concat_file = File(os.path.join(out_dir, 'concat.txt'))
    _concat(inputs=inputs, outputs=[concat_file])

    dfk.wait_for_current_tasks()


@bash_app
def _make_file(inputs=[], outputs=[], ID=''):
    commands = list()
    # commands.append(f'echo making: {ID}')

    import random
    import time
    s = random.random()
    time.sleep(s)

    for file in outputs:
        commands.append(f'echo {ID}: slept for {s:.2f} seconds >> {file}')
    return ' && '.join(commands)


@bash_app
def _concat(inputs=[], outputs=[]):
    commands = list()
    # commands.append(f'echo: concatenating')
    for file in inputs:
        commands.append(f'cat {file} >> {outputs[0]}')
    return ' && '.join(commands)


if __name__ == '__main__':
    main()
