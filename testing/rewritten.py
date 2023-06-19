import os

# from testing import make_output_dir, parsl_setup  # debug: broken on chrys?
from __init__ import make_output_dir, parsl_setup
from parsl import bash_app, python_app
from parsl.data_provider.files import File


def main():
    dfk = parsl_setup()
    out_dir = make_output_dir()

    # Create 5 files with semi-random numbers in parallel
    output_files = []
    for i in range(10):
        file = File(os.path.join(out_dir, f'{i}.txt'))
        output_files.append(
            _generate(outputs=[file])
        )

    # Concatenate the files into a single file
    input_files = list()
    for app in output_files:
        input_files.extend(app.outputs)

    cc = _concat(
        inputs=input_files,
        outputs=[File(os.path.join(out_dir, 'all.txt'))]
    )

    # Calculate the sum of the random numbers
    _total(inputs=[cc.outputs[0]])

    dfk.wait_for_current_tasks()


# App that generates a semi-random number between 0 and 32,767
@bash_app
def _generate(outputs=[]):
    import random
    import time
    sleep_time = random.random()
    time.sleep(sleep_time)
    return f'echo 1 &> {outputs[0]}'
    # return f'echo $(( RANDOM )) &> {outputs[0]}'


# App that concatenates input files into a single output file
@bash_app
def _concat(inputs=[], outputs=[]):
    return f'cat {" ".join([i.filepath for i in inputs])} > {outputs[0]}'


# App that calculates the sum of values in a list of input files
@python_app
def _total(inputs=[]):
    total = 0
    with open(inputs[0], 'r') as file:
        for line in file:
            total += int(line)
    return total


if __name__ == '__main__':
    main()
