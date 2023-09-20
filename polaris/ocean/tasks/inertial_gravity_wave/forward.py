import time

import numpy as np

from polaris.mesh.planar import compute_planar_hex_nx_ny
from polaris.ocean.model import OceanModelStep


class Forward(OceanModelStep):
    """
    A step for performing forward ocean component runs as part of inertial
    gravity wave test cases.

    Attributes
    ----------
    resolution : float
        The resolution of the test case in km
    """
    def __init__(self, component, resolution, taskdir,
                 ntasks=None, min_tasks=None, openmp_threads=1):
        """
        Create a new test case

        Parameters
        ----------
        component : polaris.Component
            The component the step belongs to

        resolution : km
            The resolution of the test case in km

        taskdir : str
            The subdirectory that the task belongs to

        ntasks : int, optional
            the number of tasks the step would ideally use.  If fewer tasks
            are available on the system, the step will run on all available
            tasks as long as this is not below ``min_tasks``

        min_tasks : int, optional
            the number of tasks the step requires.  If the system has fewer
            than this number of tasks, the step will fail

        openmp_threads : int, optional
            the number of OpenMP threads the step will use
        """
        self.resolution = resolution
        super().__init__(component=component,
                         name=f'forward_{resolution}km',
                         subdir=f'{taskdir}/{resolution}km/forward',
                         ntasks=ntasks, min_tasks=min_tasks,
                         openmp_threads=openmp_threads)

        self.add_input_file(filename='initial_state.nc',
                            target='../init/initial_state.nc')
        self.add_input_file(filename='graph.info',
                            target='../init/culled_graph.info')

        self.add_output_file(
            filename='output.nc',
            validate_vars=['layerThickness', 'normalVelocity'])

        self.add_yaml_file('polaris.ocean.config',
                           'single_layer.yaml')
        self.add_yaml_file('polaris.ocean.tasks.inertial_gravity_wave',
                           'forward.yaml')

    def compute_cell_count(self):
        """
        Compute the approximate number of cells in the mesh, used to constrain
        resources

        Returns
        -------
        cell_count : int or None
            The approximate number of cells in the mesh
        """
        section = self.config['inertial_gravity_wave']
        lx = section.getfloat('lx')
        ly = np.sqrt(3.0) / 2.0 * lx
        nx, ny = compute_planar_hex_nx_ny(lx, ly, self.resolution)
        cell_count = nx * ny
        return cell_count

    def dynamic_model_config(self, at_setup):
        """
        Set the model time step from config options at setup and runtime

        Parameters
        ----------
        at_setup : bool
            Whether this method is being run during setup of the step, as
            opposed to at runtime
        """
        super().dynamic_model_config(at_setup=at_setup)

        # dt is proportional to resolution
        config = self.config
        section = config['inertial_gravity_wave']
        dt_per_km = section.getfloat('dt_per_km')
        dt = dt_per_km * self.resolution
        # https://stackoverflow.com/a/1384565/7728169
        dt_str = time.strftime('%H:%M:%S', time.gmtime(dt))
        options = {'config_dt': dt_str}
        self.add_model_config_options(options)
