import warnings
import os
import gc

from cosmoHammer.ChainContext import ChainContext
from cosmoHammer import getLogger
from cosmoHammer.LikelihoodComputationChain import LikelihoodComputationChain as LCC
import numpy as np
from .util import Params

from py21cmfast._utils import ParameterError

logger = getLogger()

class LikelihoodComputationChain(LCC):

    def __init__(self, params, *args, **kwargs):
        self.params = params
        self._setup = False  # flag to say if this chain has been setup yet.

        super().__init__(min=params[:, 1] if params is not None else None,
                         max=params[:, 2] if params is not None else None)

    def build_model_data(self, p=None):
        """
        For a given set of parameters, generate model data for the entire core chain.

        Parameters
        ----------
        p : list or Params object, optional
            The parameters at which to evaluate the model data.

        Returns
        -------
        ctx : dict-like
            A filled context object containing all model quantities generated by core modules in the chain.

        Notes
        -----
        The data generated by this method should ideally be *deterministic*, so that input parameters map uniquely to
        output data. All data necessary to full evaluate probabilities of mock data from the model data should be
        determined in this method (including model uncertainties, if applicable).
        """
        ctx = self.createChainContext(p)

        for core in self.getCoreModules():
            core.build_model_data(ctx)

        return ctx

    def simulate_mock(self, p=None):
        """
        For a given set of parameters, generate mock data for the entire core chain.

        Parameters
        ----------
        p : list or Params object, optional
            The parameters at which to evaluate the model data. Default is to use default parameters
            of the cores.

        Returns
        -------
        ctx : dict-like
            A filled context object containing all model quantities generated by core modules in the chain.

        Notes
        -----
        The data generated by this method are *not* deterministic in general, i.e. they contain the randomness
        that is being constrained by the MCMC process. It is mock data in the sense that it should be a
        representation of the forward-model of the MCMC.
        """
        logger.debug("Simulating Mock Data... ")
        ctx = self.createChainContext(p)

        for core in self.getCoreModules():
            core.simulate_mock(ctx)

        logger.debug("   finished simulating mock data.")
        return ctx

    def addLikelihoodModule(self, module):
        """
        adds a module to the likelihood module list

        :param module: callable
            the callable module to add for the likelihood computation
        """
        self.getLikelihoodModules().append(module)
        module._LikelihoodComputationChain = self

    def addCoreModule(self, module):
        """
        adds a module to the likelihood module list

        :param module: callable
            the callable module to add for the computation of the data
        """
        self.getCoreModules().append(module)
        module._LikelihoodComputationChain = self

    def invokeCoreModule(self, coremodule, ctx):
        # Ensure that the chain is setup before invoking anything.
        if not self._setup:
            self.setup()

        logger.debug("Invoking {}...".format(os.getpid(), coremodule.__class__.__name__))
        coremodule(ctx)
        logger.debug("... finished.".format(os.getpid()))

        coremodule.prepare_storage(ctx, ctx.getData())  # This adds the ability to store stuff.

    def invokeLikelihoodModule(self, module, ctx):
        # Ensure that the chain is setup before invoking anything.
        if not self._setup:
            self.setup()

        logger.debug("Reducing data for {}...".format(module.__class__.__name__))
        model = module.reduce_data(ctx)
        logger.debug("... done reducing data")

        if hasattr(module, "store"):
            logger.debug("Storing blobs for {}...".format(module.__class__.__name__))
            module.store(model, ctx.getData())
            logger.debug("... done storing blobs.")

        logger.debug("Computing Likelihood for {}...".format(module.__class__.__name__))
        lnl = module.computeLikelihood(model)
        logger.debug("... done computing likelihood (lnl = {lnl:.3e}".format(lnl=lnl))
        return lnl

    def __call__(self, p):
        # Need to do Garbage Collection explicitly to kill the circular
        # refs that are in the this chain.
        gc.collect(2)

        try:
            return super().__call__(p)
        except ParameterError:
            return -np.inf, []

    def createChainContext(self, p=None):
        """
        Returns a new instance of a chain context
        """
        if p is None:
            p = {}

        try:
            p = Params(*zip(self.params.keys, p))
        except Exception:
            # no params or params has no keys
            pass
        return ChainContext(self, p)

    def setup(self):
        if not self._setup:
            for cModule in self.getCoreModules():
                if hasattr(cModule, "setup"):
                    cModule.setup()

            for cModule in self.getLikelihoodModules():
                if hasattr(cModule, "setup"):
                    cModule.setup()

            self._setup = True
        else:
            warnings.warn("Attempting to setup LikelihoodComputationChain when it is already setup! Ignoring...")

    def __eq__(self, other):
        if self.__class__.__name__ != other.__class__.__name__:
            return False

        if self.params != other.params:
            return False

        for thisc, thatc in zip(self.getCoreModules(), other.getCoreModules()):
            if thisc != thatc:
                return False

        for thisc, thatc in zip(self.getLikelihoodModules(), other.getLikelihoodModules()):
            if thisc != thatc:
                return False

        return True
