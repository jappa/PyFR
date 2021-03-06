# -*- coding: utf-8 -*-

from pyfr.backends.base import (BaseKernelProvider,
                                BasePointwiseKernelProvider, ComputeKernel)
from pyfr.backends.openmp.compiler import GccSourceModule
import pyfr.backends.openmp.generator as generator
import pyfr.backends.openmp.types as types
from pyfr.util import memoize


class OpenMPKernelProvider(object):
    def __init__(self, backend):
        self.backend = backend

    @memoize
    def _get_module(self, module, tplparams={}):
        # Get the template file
        tpl = self.backend.lookup.get_template(module)

        # Render the template
        mod = tpl.render(**tplparams)

        # Compile
        return GccSourceModule(mod, self.backend.cfg)

    @memoize
    def _get_function(self, module, function, restype, argtypes,
                      tplparams={}):
        # Compile off the module
        mod = self._get_module(module, tplparams)

        # Bind
        return mod.function(function, restype, argtypes)

    def _basic_kernel(self, fn, *args):
        class BasicKernel(ComputeKernel):
            def run(self):
                fn(*args)

        return BasicKernel()


class OpenMPPointwiseKernelProvider(BasePointwiseKernelProvider):
    kernel_generator_cls = generator.OpenMPKernelGenerator
    function_generator_cls = generator.OpenMPFunctionGenerator

    @memoize
    def _build_kernel(self, name, src, argtypes):
        mod = GccSourceModule(src, self.backend.cfg)
        return mod.function(name, None, argtypes)

    def _build_arglst(self, dims, argn, argt, argdict):
        # First arguments are the dimensions
        ndim, arglst = len(dims), list(dims)

        # Matrix types
        mattypes = (types.OpenMPMatrixBank, types.OpenMPMatrixBase)

        # Process non-dimensional arguments
        for aname, atypes in zip(argn[ndim:], argt[ndim:]):
            ka = argdict[aname]

            # Matrix
            if isinstance(ka, mattypes):
                arglst += [ka, ka.leadsubdim] if len(atypes) == 2 else [ka]
            # MPI view
            elif isinstance(ka, types.OpenMPMPIView):
                arglst += [ka.view.mapping, ka.view.strides]
            # View
            elif isinstance(ka, types.OpenMPView):
                arglst += [ka.mapping, ka.strides]
            # Other; let ctypes handle it
            else:
                arglst.append(ka)

        return arglst

    def _instantiate_kernel(self, dims, fun, arglst):
        class PointwiseKernel(ComputeKernel):
            def run(self):
                fun(*arglst)

        return PointwiseKernel()
