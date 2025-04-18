import argparse
import logging
import os
import platform
import subprocess
import sys
from urllib.request import Request, urlopen


def parse_args(bootstrap):
    """
    Parse arguments from the configure conda environment script call

    Parameters
    ----------
    bootstrap : bool
        Whether the environment being set up is a bootstrap environment

    Returns
    -------
    args : list[str]
        A list of each command-line argument provided in the call to the
        configure conda environment script
    """

    parser = argparse.ArgumentParser(
        description='Deploy a polaris conda environment'
    )
    parser.add_argument(
        '-m',
        '--machine',
        dest='machine',
        help='The name of the machine for loading machine-'
        'related config options.',
    )
    parser.add_argument(
        '--conda', dest='conda_base', help='Path to the conda base.'
    )
    parser.add_argument(
        '--spack', dest='spack_base', help='Path to the spack base.'
    )
    parser.add_argument(
        '--env_name',
        dest='conda_env_name',
        help='The conda environment name and activation script prefix.',
    )
    parser.add_argument(
        '-p',
        '--python',
        dest='python',
        type=str,
        help='The python version to deploy.',
    )
    parser.add_argument(
        '-c',
        '--compiler',
        dest='compilers',
        type=str,
        nargs='*',
        help='The name of the compiler(s).',
    )
    parser.add_argument(
        '-i',
        '--mpi',
        dest='mpis',
        type=str,
        nargs='*',
        help='The MPI library (or libraries) to deploy, see '
        'the docs for details.',
    )
    parser.add_argument(
        '--conda_env_only',
        dest='conda_env_only',
        action='store_true',
        help='Create only the conda environment for running '
        'polaris tasks (without compilers or libraries '
        'for building E3SM components).',
    )
    parser.add_argument(
        '--recreate',
        dest='recreate',
        action='store_true',
        help='Recreate the environment if it exists.',
    )
    parser.add_argument(
        '--update_jigsaw',
        dest='update_jigsaw',
        action='store_true',
        help='Reinstall JIGSAW even if not recreating conda environment.',
    )
    parser.add_argument(
        '-f',
        '--config_file',
        dest='config_file',
        help='Config file to override deployment config options.',
    )
    parser.add_argument(
        '--check',
        dest='check',
        action='store_true',
        help='Check the resulting environment for expected packages.',
    )
    parser.add_argument(
        '--use_local',
        dest='use_local',
        action='store_true',
        help='Use locally built conda packages (for testing).',
    )
    parser.add_argument(
        '--mache_fork',
        dest='mache_fork',
        help='Point to a mache fork (and branch) for testing.',
    )
    parser.add_argument(
        '--mache_branch',
        dest='mache_branch',
        help='Point to a mache branch (and fork) for testing.',
    )
    parser.add_argument(
        '--update_spack',
        dest='update_spack',
        action='store_true',
        help='If the shared spack environment should be created or recreated.',
    )
    parser.add_argument(
        '--tmpdir',
        dest='tmpdir',
        help='A temporary directory for building spack packages.',
    )
    parser.add_argument(
        '--with_albany',
        dest='with_albany',
        action='store_true',
        help='Whether to include albany in the spack environment.',
    )
    parser.add_argument(
        '--with_petsc',
        dest='with_petsc',
        action='store_true',
        help='Whether to include PETSc and Netlib-LAPACK in '
        'the spack environment.',
    )
    parser.add_argument(
        '--without_openmp',
        dest='without_openmp',
        action='store_true',
        help='If this flag is included, OPENMP=false will '
        'be added to the load script.  By default, MPAS '
        'builds will be with OpenMP (OPENMP=true).',
    )
    parser.add_argument(
        '--verbose',
        dest='verbose',
        action='store_true',
        help='Print all output to the terminal, rather than '
        'log files (usually for debugging).',
    )
    if bootstrap:
        parser.add_argument(
            '--local_conda_build',
            dest='local_conda_build',
            type=str,
            help='A path for conda packages (for testing).',
        )

    args = parser.parse_args(sys.argv[1:])

    if (args.mache_fork is None) != (args.mache_branch is None):
        raise ValueError(
            'You must supply both or neither of '
            '--mache_fork and --mache_branch'
        )

    return args


def get_conda_base(conda_base, config, shared=False, warn=False):
    """
    Get the absolute path to the files for the conda base environment

    Parameters
    ----------
    conda_base : str
        The relative or absolute path to the conda base files

    config : ConfigParser
        Config object

    shared : bool, optional
        Whether we are working in a shared conda environment

    warn : bool, optional
        Whether to print a warning that the conda path was not supplied

    Returns
    -------
    conda_base : str
        Path to the conda base environment
    """

    if shared:
        conda_base = config.get('paths', 'polaris_envs')
    elif conda_base is None:
        try:
            conda_base = subprocess.check_output(
                ['conda', 'info', '--base'], text=True
            ).strip()
            if warn:
                print(
                    f'\nWarning: --conda path not supplied.  Using conda '
                    f'installed at:\n'
                    f'   {conda_base}\n'
                )
        except subprocess.CalledProcessError as e:
            raise ValueError(
                'No conda base provided with --conda and '
                'none could be inferred.'
            ) from e
    # handle "~" in the path
    conda_base = os.path.abspath(os.path.expanduser(conda_base))
    return conda_base


def check_call(commands, env=None, logger=None):
    """
    Wrapper for making a shell call with logging and error management

    Parameters
    ----------
    commands : list[str]
        A list of each command given as a string

    env : Mapping[str, str], optional
        Any environment variables required for the command

    logger : logging.Logger, optional
        The logger for output
    """

    command_list = commands.replace(' && ', '; ').split('; ')
    print_command = '\n   '.join(command_list)
    if logger is None:
        print(f'\n Running:\n   {print_command}\n')
    else:
        logger.info(f'\nrunning:\n   {print_command}\n')

    if logger is None:
        process = subprocess.Popen(
            commands, env=env, executable='/bin/bash', shell=True
        )
        process.wait()
    else:
        process = subprocess.Popen(
            commands,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            executable='/bin/bash',
            shell=True,
        )
        stdout, stderr = process.communicate()

        if stdout:
            stdout_decoded = stdout.decode('utf-8')
            for line in stdout_decoded.split('\n'):
                logger.info(line)
        if stderr:
            stderr_decoded = stderr.decode('utf-8')
            for line in stderr_decoded.split('\n'):
                logger.error(line)

    if process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode, commands)


def install_miniforge(conda_base, activate_base, logger):
    """
    Install Miniforge if it isn't installed already

    Parameters
    ----------
    conda_base : str
        Absolute path to the conda base environment files

    activate_base : str
        Command to activate the conda base environment

    logger : logging.Logger
        The logger for output
    """

    if not os.path.exists(conda_base):
        print('Installing Miniforge3')
        if platform.system() == 'Darwin':
            system = 'MacOSX'
        else:
            system = 'Linux'
        miniforge = f'Miniforge3-{system}-x86_64.sh'
        url = f'https://github.com/conda-forge/miniforge/releases/latest/download/{miniforge}'  # noqa: E501
        print(url)
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        f = urlopen(req)
        html = f.read()
        with open(miniforge, 'wb') as outfile:
            outfile.write(html)
        f.close()

        command = f'/bin/bash {miniforge} -b -p {conda_base}'
        check_call(command, logger=logger)
        os.remove(miniforge)

    print('Doing initial setup\n')
    commands = (
        f'{activate_base} && '
        f'conda config --add channels conda-forge && '
        f'conda config --set channel_priority strict && '
        f'conda update -y --all && '
        f'conda init --no-user'
    )

    check_call(commands, logger=logger)


def get_logger(name, log_filename):
    """
    Get the logger for logging output

    Parameters
    ----------
    name : str
        Name of the logger

    log_filename : str
        Filepath for the logging file

    Returns
    -------
    logger : logging.Logger
        The logger for output
    """

    print(f'Logging to: {log_filename}\n')
    try:
        os.remove(log_filename)
    except FileNotFoundError:
        pass
    logger = logging.getLogger(name)
    handler = logging.FileHandler(log_filename)
    formatter = PolarisFormatter()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


class PolarisFormatter(logging.Formatter):
    """
    A custom formatter for logging
    Modified from:
    https://stackoverflow.com/a/8349076/7728169
    https://stackoverflow.com/a/14859558/7728169
    """

    # printing error messages without a prefix because they are sometimes
    # errors and sometimes only warnings sent to stderr
    dbg_fmt = 'DEBUG: %(module)s: %(lineno)d: %(msg)s'
    info_fmt = '%(msg)s'
    err_fmt = info_fmt

    def __init__(self, fmt=info_fmt):
        self._fmt = None
        logging.Formatter.__init__(self, fmt)

    def format(self, record):
        # Save the original format configured by the user
        # when the logger formatter was instantiated
        format_orig = self._fmt

        # Replace the original format with one customized by logging level
        if record.levelno == logging.DEBUG:
            self._fmt = PolarisFormatter.dbg_fmt

        elif record.levelno == logging.INFO:
            self._fmt = PolarisFormatter.info_fmt

        elif record.levelno == logging.ERROR:
            self._fmt = PolarisFormatter.err_fmt

        # Call the original formatter class to do the grunt work
        result = logging.Formatter.format(self, record)

        # Restore the original format configured by the user
        self._fmt = format_orig

        return result
