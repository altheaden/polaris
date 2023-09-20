import datetime
import warnings

import cmocean  # noqa: F401
import numpy as np
import xarray as xr

from polaris import Step
from polaris.ocean.tasks.inertial_gravity_wave.exact_solution import (
    ExactSolution,
)


class Analysis(Step):
    """
    A step for analysing the output from the inertial gravity wave
    test case

    Attributes
    ----------
    resolutions : list of int
        The resolutions of the meshes that have been run
    """
    def __init__(self, component, resolutions, taskdir):
        """
        Create the step

        Parameters
        ----------
        component : polaris.Component
            The component the step belongs to

        resolutions : list of int
            The resolutions of the meshes that have been run

        taskdir : str
            The subdirectory that the task belongs to
        """
        super().__init__(component=component, name='analysis', indir=taskdir)
        self.resolutions = resolutions

        for resolution in resolutions:
            self.add_input_file(
                filename=f'init_{resolution}km.nc',
                target=f'../{resolution}km/init/initial_state.nc')
            self.add_input_file(
                filename=f'output_{resolution}km.nc',
                target=f'../{resolution}km/forward/output.nc')

    def run(self):
        """
        Run this step of the test case
        """
        config = self.config
        resolutions = self.resolutions

        section = config['inertial_gravity_wave']
        conv_thresh = section.getfloat('conv_thresh')
        conv_max = section.getfloat('conv_max')

        rmse = []
        for i, res in enumerate(resolutions):
            init = xr.open_dataset(f'init_{res}km.nc')
            ds = xr.open_dataset(f'output_{res}km.nc')
            exact = ExactSolution(init, config)

            t0 = datetime.datetime.strptime(ds.xtime.values[0].decode(),
                                            '%Y-%m-%d_%H:%M:%S')
            tf = datetime.datetime.strptime(ds.xtime.values[-1].decode(),
                                            '%Y-%m-%d_%H:%M:%S')
            t = (tf - t0).total_seconds()
            ssh_model = ds.ssh.values[-1, :]
            rmse.append(np.sqrt(np.mean((ssh_model - exact.ssh(t).values)**2)))

        p = np.polyfit(np.log10(resolutions), np.log10(rmse), 1)
        conv = p[0]

        if conv < conv_thresh:
            raise ValueError(f'order of convergence '
                             f' {conv} < min tolerence {conv_thresh}')

        if conv > conv_max:
            warnings.warn(f'order of convergence '
                          f'{conv} > max tolerence {conv_max}')
