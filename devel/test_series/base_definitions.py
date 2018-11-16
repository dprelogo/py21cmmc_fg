from py21cmmc.mcmc import CoreLightConeModule, run_mcmc as _run_mcmc
from py21cmmc_fg.core import CoreInstrumental, CorePointSourceForegrounds #, ForegroundsBase
from py21cmmc_fg.likelihood import LikelihoodInstrumental2D
import numpy as np
import os

DEBUG = int(os.environ.get("DEBUG", 0))

if DEBUG>2 or DEBUG<0:
    raise ValueError("DEBUG should be 0,1,2")

import logging

logger = logging.getLogger("21CMMC")

logger.setLevel([logging.DEBUG, logging.INFO, logging.WARNING][-DEBUG])

if DEBUG:
    logger.debug("Running in DEBUG=%s mode."%DEBUG)

# ============== SET THESE VARIABLES.


# ----- These should be kept the same between all tests. -------
freq_min = 150.0
freq_max = 160.0
z_step_factor = 1.04
sky_size = 3.0   # in sigma
max_tile_n = 50
taper = np.blackman
integration_time = 1200
tile_diameter = 4.0

# MCMC OPTIONS
params=dict(  # Parameter dict as described above.
            HII_EFF_FACTOR=[30.0, 10.0, 50.0, 3.0],
            ION_Tvir_MIN=[4.7, 2, 8, 0.1],
        )


# ----- Options that differ between DEBUG levels --------
HII_DIM = [250, 80, 80][DEBUG]
DIM = 3 * HII_DIM
BOX_LEN = 3 * HII_DIM

# Instrument Options
nfreq = 32 if DEBUG else 64
n_cells = 300 if DEBUG else 500

# Likelihood options
if DEBUG==2:
    n_ubins = 21
else:
    n_ubins = 40

# ============== END OF USER-SETTABLE STUFF

z_min = 1420./freq_max - 1
z_max = 1420./freq_min - 1

core_eor = CoreLightConeModule(
    redshift = z_min,              # Lower redshift of the lightcone
    max_redshift = z_max,          # Approximate maximum redshift of the lightcone (will be exceeded).
    user_params = dict(
        HII_DIM = HII_DIM,
        BOX_LEN = BOX_LEN,
        DIM=DIM
    ),
    z_step_factor=z_step_factor,          # How large the steps between evaluated redshifts are (log).
    regenerate=False,
    keep_data_in_memory=DEBUG
)


class CustomCoreInstrument(CoreInstrumental):
    def __init__(self, freq_min=freq_min, freq_max = freq_max, nfreq=nfreq,
                 sky_size=sky_size, n_cells = n_cells, tile_diameter=tile_diameter,
                 integration_time = integration_time,
                 **kwargs):
        super().__init__(freq_max=freq_max, freq_min=freq_min,
                         nfreq=nfreq, tile_diameter=tile_diameter, integration_time=integration_time,
                         sky_extent=sky_size, n_cells=n_cells,
                         **kwargs)


class CustomLikelihood(LikelihoodInstrumental2D):
    def __init__(self, n_ubins=n_ubins, uv_max=None, frequency_taper=taper, **kwargs):
        super().__init__(n_ubins=n_ubins, uv_max=uv_max, frequency_taper=frequency_taper,
                         simulate=True,
                         **kwargs)

    def store(self, model, storage):
        """Store stuff"""
        storage['signal'] = model[0]['p_signal'] + self.noise['mean']

        # Remember that the variance is actually the variance plus the model uncertainty
        sig_cov = self.get_signal_covariance(model[0]['p_signal'])

        # Add a "number of sigma" entry
        var = np.array([np.diag(p) + np.diag(s) for p,s in zip(self.noise['covariance'], sig_cov)])
        storage['sigma'] = (self.data['p_signal'] - self.noise['mean'] - model[0]['p_signal'])/np.sqrt(var)


def run_mcmc(*args, model_name, params=params, **kwargs):
    return _run_mcmc(
        *args,
        datadir='data',                        # Directory for all outputs
        model_name=model_name,                 # Filename of main chain output
        params=params,
        walkersRatio=[18,3,2][DEBUG],       # The number of walkers will be walkersRatio*nparams
        burninIterations=0,                    # Number of iterations to save as burnin. Recommended to leave as zero.
        sampleIterations=[100, 50, 2][DEBUG],  # Number of iterations to sample, per walker.
        threadCount=[12,6,1][DEBUG],        # Number of processes to use in MCMC (best as a factor of walkersRatio)
        continue_sampling=False,                # Whether to contine sampling from previous run *up to* sampleIterations.
        **kwargs
    )
