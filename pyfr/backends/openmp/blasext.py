# -*- coding: utf-8 -*-

import numpy as np

from pyfr.backends.openmp.provider import OpenMPKernelProvider
from pyfr.backends.base import ComputeKernel


class OpenMPBlasExtKernels(OpenMPKernelProvider):
    def axnpby(self, y, *xn):
        if any(y.traits != x.traits for x in xn):
            raise ValueError('Incompatible matrix types')

        opts = dict(n=len(xn), fpdtype=y.dtype)
        fn = self._get_function('axnpby', 'axnpby', None,
                                [np.int32] + [np.intp, y.dtype]*(1 + len(xn)),
                                opts)

        class AxnpbyKernel(ComputeKernel):
            def run(self, beta, *alphan):
                args = [i for axn in zip(xn, alphan) for i in axn]
                fn(y.leaddim*y.nrow, y, beta, *args)

        return AxnpbyKernel()
