import argparse
import glob
import os
import subprocess
import sys
import time

import parsl
from mpas_tools.logging import LoggingContext
from parsl import python_app
from parsl.config import Config
from parsl.data_provider.files import File
from parsl.dataflow.futures import AppFuture
from parsl.executors import HighThroughputExecutor
from parsl.launchers import SimpleLauncher
from parsl.providers import LocalProvider

from polaris.logging import log_method_call
from polaris.parallel import (
    get_available_parallel_resources,
    get_parallel_command,
)
from polaris.run import (
    load_dependencies,
    pickle_step_after_run,
    serial,
    setup_config,
    unpickle_suite,
)


def run_tests(suite_name, partition=None, nodes=1, walltime='01:00:00'):
    """
    Run the given test suite in task parallel

    Parameters
    ----------
    suite_name : str
        The name of the test suite

    partition : str

    nodes : int

    walltime : str
    """
    test_suite = unpickle_suite(suite_name)

    # get the config file for the first test case in the suite
    test_case = next(iter(test_suite['test_cases'].values()))
    config_filename = os.path.join(test_case.work_dir,
                                   test_case.config_filename)
    config = setup_config(config_filename)
    available_resources = get_available_parallel_resources(config)

    parsl.clear()
    executor = _create_executor()
    dfk = parsl.load(executor)  # returns Parsl data flow kernel

    with LoggingContext(suite_name) as stdout_logger:

        os.environ['PYTHONUNBUFFERED'] = '1'
        test_cases = test_suite['test_cases']

        # start timing suite execution
        suite_start = time.time()

        app_futures = _setup_apps(test_cases, available_resources)

        # test_times = dict.fromkeys(app_futures, None)

        # all_complete = False
        # while not all_complete:
        #     all_complete = True
        #     for app_name, app in app_futures.items():
        #         if app is not None:
        #             if app.done():
        #                 try:
        #                     test_time = app.result()
        #                     # TODO: debug
        #                     print(f'{app_name} finished.')
        #                 except Exception:
        #                     # TODO: debug
        #                     print(f'{app_name} failed.')
        #                     test_time = None
        #                 app_futures[app_name] = None
        #                 test_times[app_name] = test_time
        #             else:
        #                 all_complete = False

        dfk.wait_for_current_tasks()

        # execution complete
        suite_time = time.time() - suite_start
        # TODO: debug
        print(f"Ran all test cases in {suite_time:.2f} seconds:")

        # rt_sum = 0
        # for test_name, test_time in test_times.items():
        #     if test_time is not None:
        #         rt_sum += test_time
        #         # TODO: debug
        #         print(f'\t{test_name} completed in {test_time:.2f} seconds.')
        #     else:
        #         # TODO: debug
        #         print(f'\t{test_name} failed.')

        rt_sum = 0
        for test_name, steps in app_futures.items():
            print(f'{test_name}')
            for step_name, app in steps.items():
                try:
                    step_time = app.result()
                    rt_sum += step_time
                    print(f'  * step: {step_name} passed in {step_time:.2f}s')
                except Exception:
                    print(f'  * step: {step_name} failed')

        print(f'Cumulative test test_time: {rt_sum:.2f}')

        exit()  # TODO: Debug only :)

        failures = 0
        cwd = os.getcwd()
        test_times = dict()
        success_strs = dict()

        for test_name in test_suite['test_cases']:
            test_case = test_suite['test_cases'][test_name]
            _log_and_run_test(test_name, test_case, test_times, success_strs,
                              stdout_logger)
            if not success_strs[test_name]:
                failures += 1

        os.chdir(cwd)

        stdout_logger.info('Test Runtimes:')
    for test_name, test_time in test_times.items():
        secs = round(test_time)
        mins = secs // 60
        secs -= 60 * mins
        stdout_logger.info(f'{mins:02d}:{secs:02d} '
                           f'{success_strs[test_name]} {test_name}')
    secs = round(suite_time)
    mins = secs // 60
    secs -= 60 * mins
    stdout_logger.info(f'Total runtime {mins:02d}:{secs:02d}')

    if failures == 0:
        stdout_logger.info('PASS: All passed successfully!')
    else:
        if failures == 1:
            message = '1 test'
        else:
            message = f'{failures} tests'
        stdout_logger.error(f'FAIL: {message} failed, see above.')
        sys.exit(1)


def main():

    parser = argparse.ArgumentParser(
        description='Run a test suite, test case or step',
        prog='polaris run')
    parser.add_argument("suite", nargs='?',
                        help="The name of a test suite to run. Can exclude "
                             "or include the .pickle filename suffix.")
    parser.add_argument("--steps", dest="steps", nargs='+',
                        help="The steps of a test case to run")
    parser.add_argument("--no-steps", dest="no_steps", nargs='+',
                        help="The steps of a test case not to run, see "
                             "steps_to_run in the config file for defaults.")
    parser.add_argument("--substep", dest="substep",
                        help="The substep of a step to run")

    args = parser.parse_args(sys.argv[2:])

    if args.suite is not None:
        run_tests(args.suite)
    elif os.path.exists('test_case.pickle'):
        # Running a test case inside of its work directory
        run_tests(suite_name='test_case')
    elif os.path.exists('step.pickle'):
        # Running a step inside of its work directory
        serial.run_single_step(args.step_is_subprocess)
    else:
        pickles = glob.glob('*.pickle')
        if len(pickles) == 1:
            suite = os.path.splitext(os.path.basename(pickles[0]))[0]
            run_tests(suite)
        elif len(pickles) == 0:
            raise OSError('No pickle files were found. Are you sure this is '
                          'a polaris suite, test-case or step work directory?')
        else:
            raise ValueError('More than one suite was found. Please specify '
                             'which to run: polaris run <suite>')


def _create_executor(nodes=1):
    """
    Create a Parsl executor
    """
    config = Config(
        executors=[
            HighThroughputExecutor(
                label='Polaris_HTEX',
                worker_debug=True,
                start_method='spawn',
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


@python_app
def _run_step_app(test_case, step, parallel_args, inputs=[], outputs=[]):
    import os
    import time

    from mpas_tools.logging import LoggingContext

    start_time = time.time()

    log_filename = os.path.join(step.work_dir, f'{step.name}.log')
    with LoggingContext(name=step.path,
                        log_filename=log_filename) as logger:
        logger.info(f'running: {step.name} in {step.work_dir}')  # TODO: debug

        for file in inputs:
            logger.info(f' <- input file: {file.filepath}')  # TODO: debug

        for file in outputs:
            logger.info(f' -> output file: {file.filepath}')  # TODO: debug

        if step.args is not None:
            _pre_run(test_case=test_case, step=step)

        _run_step(
            parallel_args=parallel_args,
            work_dir=step.work_dir
        )

        _post_run(test_case=test_case, step=step)

        return time.time() - start_time


def _pre_run(test_case, step):
    load_dependencies(test_case, step)
    os.chdir(step.work_dir)
    step.runtime_setup()


def _run_step(parallel_args=[], work_dir=''):
    parallel_args = ' '.join(parallel_args)
    parallel_args = f'cd {work_dir} && {parallel_args}'
    subprocess.run(args=parallel_args, check=True, shell=True)


def _post_run(test_case=None, step=None):
    pickle_step_after_run(test_case, step)


def _setup_apps(test_cases, available_resources):
    """

    Parameters
    ----------
    test_cases : dict
    available_resources : dict

    Returns
    -------
    app_futures : dict

    """

    # Constrain resources before we run anything
    for test_name, test_case in test_cases.items():
        for step_name, step in test_case.steps.items():
            step.constrain_resources(available_resources)

    data_futures: dict[str, File] = dict()
    app_futures: dict[str, dict[str, AppFuture]] = dict()

    for test_name, test_case in test_cases.items():
        app_futures[test_name] = dict()

        for step_name, step in test_case.steps.items():
            if step.args is not None:
                args = step.args
            else:
                args = ['polaris', 'serial', '--steps', step_name,
                        '--step_is_subprocess']
            parallel_args = get_parallel_command(
                args, step.cpus_per_task, step.ntasks, step.config)

            app_inputs, app_outputs = _get_app_dependencies(
                step=step,
                data_futures=data_futures
            )

            app = _run_step_app(
                test_case=test_case,
                step=step,
                parallel_args=parallel_args,
                inputs=app_inputs,
                outputs=app_outputs
            )

            for file in app.outputs:
                # Add all output data futures to the shared dictionary to
                #   be found by any dependencies
                data_futures[file.filepath] = file

            app_futures[test_name][step_name] = app

    return app_futures


def _get_app_dependencies(step, data_futures):
    app_inputs: list[File] = list()
    missing_files: list[str] = list()
    for filename in step.inputs:
        if filename in data_futures:
            # if this input file is dependent on another app, its data
            #   future will already exist
            file = data_futures[filename]
        else:
            # otherwise, check if the file exists, but is not a dependency of a
            #   previous step (e.g., component model files), and make a new
            #   data future for it
            if os.path.exists(filename):
                file = File(filename)
            else:
                missing_files.append(filename)
        app_inputs.append(file)

    if len(missing_files) > 0:
        raise OSError(
            f'input file(s) missing in step {step.name} of '
            f'{step.component.name}/{step.test_group.name}/'
            f'{step.test_case.subdir}: {missing_files}')

    app_outputs: list[File] = list()
    for filename in step.outputs:
        file = File(filename)
        app_outputs.append(file)

    return app_inputs, app_outputs


def _log_and_run_test(test_name, test_case, test_times, success_strs,
                      stdout_logger):
    """
    Run a single test

    Parameters
    ----------
    test_name : str
        The name of the test case

    test_case : polaris.TestCase
        The test case to set up

    test_times : dict
        Dictionary of test times

    success_strs : dict
        Dictionary of success strings of tests

    stdout_logger : mpas-tools.logging.LoggingContext

    """
    # ANSI fail text: https://stackoverflow.com/a/287944/7728169
    start_fail = '\033[91m'
    start_pass = '\033[92m'
    end = '\033[0m'
    pass_str = f'{start_pass}PASS{end}'
    success_strs_str = f'{start_pass}success_strs{end}'
    fail_str = f'{start_fail}FAIL{end}'
    error_str = f'{start_fail}ERROR{end}'

    test_name = test_case.path.replace('/', '_')
    stdout_logger.info(f"{test_name}")

    test_name = test_case.path.replace('/', '_')
    test_case.stdout_logger = None
    test_case.logger = stdout_logger

    # Task parallel implies the values of these booleans
    test_case.new_step_log_file = True
    test_case.print_substeps = False

    os.chdir(test_case.work_dir)

    test_case.steps_to_run = test_case.config.get(
        'test_case', 'steps_to_run').replace(',', ' ').split()

    test_start = time.time()
    try:
        run_status = success_strs_str
        test_pass = True
    except BaseException:
        run_status = error_str
        test_pass = False
        stdout_logger.exception('Exception raised while running '
                                'the steps of the test case')

    # Run validation
    if test_pass:
        with LoggingContext(
                name="validation",
                log_filename="validation.log") as valid_logger:
            test_case.logger = valid_logger
            valid_logger.info('')
            log_method_call(method=test_case.validate,
                            logger=valid_logger)
            valid_logger.info('')
            try:
                test_case.validate()
            except BaseException:
                run_status = error_str
                test_pass = False
                valid_logger.exception('Exception raised in the test '
                                       'case\'s validate() method')

    baseline_status = None
    internal_status = None
    if test_case.validation is not None:
        internal_pass = test_case.validation['internal_pass']
        baseline_pass = test_case.validation['baseline_pass']

        if internal_pass is not None:
            if internal_pass:
                internal_status = pass_str
            else:
                internal_status = fail_str
                stdout_logger.exception(
                    'Internal test case validation failed')
                test_pass = False

        if baseline_pass is not None:
            if baseline_pass:
                baseline_status = pass_str
            else:
                baseline_status = fail_str
                stdout_logger.exception('Baseline validation failed')
                test_pass = False

    status = f'  test execution:      {run_status}'
    if internal_status is not None:
        status = f'{status}\n  test validation:     {internal_status}'
    if baseline_status is not None:
        status = f'{status}\n  baseline comparison: {baseline_status}'

    if test_pass:
        stdout_logger.info(status)
        success_strs[test_name] = pass_str
    else:
        stdout_logger.error(status)
        stdout_logger.error(f'  see log files in: {test_case.path}')
        success_strs[test_name] = fail_str

    test_times[test_name] = time.time() - test_start
