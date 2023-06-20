import os

# from testing import make_output_dir, parsl_setup  # debug: broken on chrys?
from __init__ import make_output_dir, parsl_setup
from parsl import bash_app
from parsl.data_provider.files import File
from test_objects import Step


def main():
    """
    We have groups of filenames for files we wish to create.
    Some of these filenames depend on each other.
    """
    dfk = parsl_setup()
    out_dir = make_output_dir()

    # data creation
    steps = list()
    concat_filenames = list()
    for i in range(20):
        step1 = Step(name=f'{i}_first')
        step1.add_input_file(os.path.join(out_dir, f'{step1.name}_in.txt'))
        step1.add_output_file(os.path.join(out_dir, f'{step1.name}_out.txt'))
        steps.append(step1)

        step2 = Step(name=f'{i}_second')
        step2.add_input_file(os.path.join(out_dir, f'{step1.name}_out.txt'))
        step2.add_output_file(os.path.join(out_dir, f'{step2.name}_out.txt'))
        concat_filenames.extend(step2.outputs)
        steps.append(step2)

    concat_step = Step(name='concatenate')
    concat_step.add_input_files(concat_filenames)
    concat_step.add_output_file(os.path.join(out_dir, 'concat.txt'))
    steps.append(concat_step)

    # parsl stuff
    data_futures: dict[str, File] = dict()
    for step in steps:

        app_inputs = list()
        for filename in step.inputs:
            if filename in data_futures:
                file = data_futures[filename]
            else:
                file = File(filename)
            app_inputs.append(file)
            data_futures[file.filepath] = file

        app_outputs = list()
        for filename in step.outputs:
            file = File(filename)
            app_outputs.append(file)
            data_futures[file.filepath] = file

        if step.name == 'concatenate':
            _concat(inputs=app_inputs, outputs=app_outputs)
        else:
            _make_files(inputs=app_inputs, outputs=app_outputs, ID=step.name)

        # for file in app.outputs:
        #     data_futures[file.filepath] = file

    dfk.wait_for_current_tasks()


@bash_app
def _make_files(inputs=[], outputs=[], ID=''):
    commands = list()

    import random
    s = random.random()
    commands.append(f'sleep {s}')

    for i in range(len(inputs)):
        commands.append(f'echo data from {inputs[i].filepath} >> {outputs[i]}')

    return ' && '.join(commands)


@bash_app
def _concat(inputs=[], outputs=[]):
    commands = list()
    for file in inputs:
        commands.append(f'cat {file} >> {outputs[0]}')
    return ' && '.join(commands)


if __name__ == '__main__':
    main()
