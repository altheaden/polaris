import os

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

    # data creation
    steps = list()
    concat_filenames = list()
    for i in range(20):
        step1 = _make_step(out_dir=out_dir, name=f'{i}_first')
        steps.append(step1)

        step2 = _make_dependent_step(out_dir=out_dir, name=f'{i}_second',
                                     dependency_name=f'{i}_first')
        steps.append(step2)
        concat_filenames.extend(step2['outputs'])

    steps.append(_make_concat_step(out_dir=out_dir, name='concat',
                                   input_filenames=concat_filenames))

    # parsl stuff
    data_futures: dict[str, File] = dict()
    for step in steps:

        app_inputs = list()
        for filename in step['inputs']:
            if filename in data_futures:
                file = data_futures[filename]
            else:
                file = File(filename)
            app_inputs.append(file)

        app_outputs = list()
        for filename in step['outputs']:
            file = File(filename)
            app_outputs.append(file)

        if step['name'] == 'concatenate':
            app = _concat(inputs=app_inputs, outputs=app_outputs)
        else:
            app = _make_files(inputs=app_inputs, outputs=app_outputs,
                              ID=step['name'])

        for file in app.outputs:
            data_futures[file.filepath] = file

    dfk.wait_for_current_tasks()


def _make_step(out_dir, name):
    step = dict()
    step['name'] = name
    step['inputs'] = [
        os.path.join(out_dir, f'{name}_in.txt'),
    ]
    step['outputs'] = [
        os.path.join(out_dir, f'{name}_out.txt'),
    ]
    return step


def _make_dependent_step(out_dir, dependency_name, name):
    step = dict()
    step['name'] = name
    step['inputs'] = [
        os.path.join(out_dir, f'{dependency_name}_out.txt'),
    ]
    step['outputs'] = [
        os.path.join(out_dir, f'{name}_out.txt'),
    ]
    return step


def _make_concat_step(out_dir, input_filenames, name):
    step = dict()
    step['name'] = name
    step['inputs'] = input_filenames
    step['outputs'] = [
        os.path.join(out_dir, 'concat.txt')
    ]
    return step


def _add_to_data_futures(data_futures, app):
    for file in app.outputs:
        data_futures[file.filename] = file


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
