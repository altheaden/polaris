from polaris.ocean.model import OceanModelStep


class Forward(OceanModelStep):
    """
    A step for performing forward ocean component runs as part of baroclinic
    channel test cases.

    Attributes
    ----------
    resources_fixed : bool
        Whether resources were set already and shouldn't be updated
        algorithmically

    dt : float
        The model time step in seconds

    btr_dt : float
        The model barotropic time step in seconds
    """
    def __init__(self, component, name='forward', subdir=None, indir=None,
                 ntasks=None, min_tasks=None, openmp_threads=1,
                 validate_vars=None):
        """
        Create a new test case

        Parameters
        ----------
        component : polaris.Component
            The component the step belongs to

        name : str
            the name of the test case

        subdir : str, optional
            the subdirectory for the step.  If neither this nor ``indir``
             are provided, the directory is the ``name``

        indir : str, optional
            the directory the step is in, to which ``name`` will be appended

        ntasks : int, optional
            the number of tasks the step would ideally use.  If fewer tasks
            are available on the system, the step will run on all available
            tasks as long as this is not below ``min_tasks``

        min_tasks : int, optional
            the number of tasks the step requires.  If the system has fewer
            than this number of tasks, the step will fail

        openmp_threads : int, optional
            the number of OpenMP threads the step will use

        validate_vars : list, optional
            A list of variable names to compare with a baseline (if one is
            provided)
        """
        super().__init__(component=component, name=name, subdir=subdir,
                         indir=indir, ntasks=ntasks, min_tasks=min_tasks,
                         openmp_threads=openmp_threads)

        self.add_yaml_file('polaris.ocean.config', 'output.yaml')

        self.add_input_file(filename='initial_state.nc',
                            target='../init/initial_state.nc')
        self.add_input_file(filename='forcing.nc',
                            target='../init/forcing.nc')
        self.add_input_file(filename='graph.info',
                            target='../init/culled_graph.info')

        self.add_yaml_file('polaris.ocean.tasks.single_column',
                           'forward.yaml')

        self.add_output_file(filename='output.nc', validate_vars=validate_vars)

        self.resources_fixed = (ntasks is not None)

        self.dt = None
        self.btr_dt = None
