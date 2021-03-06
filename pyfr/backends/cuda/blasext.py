# -*- coding: utf-8 -*-

import numpy as np

from pyfr.backends.cuda.provider import CUDAKernelProvider, get_grid_for_block
from pyfr.backends.base import ComputeKernel
from pyfr.nputil import npdtype_to_ctype


class CUDABlasExtKernels(CUDAKernelProvider):
    def axnpby(self, y, *xn):
        if any(y.traits != x.traits for x in xn):
            raise ValueError('Incompatible matrix types')

        opts = dict(n=len(xn), dtype=npdtype_to_ctype(y.dtype))
        fn = self._get_function('axnpby', 'axnpby', [np.int32] +
                                [np.intp, y.dtype]*(1 + len(xn)), opts)

        # Determine the total element count in the matrices
        cnt = y.leaddim*y.nrow

        # Compute a suitable block and grid
        block = (1024, 1, 1)
        grid = get_grid_for_block(block, cnt)

        class AxnpbyKernel(ComputeKernel):
            def run(self, scomp, scopy, beta, *alphan):
                args = [i for axn in zip(xn, alphan) for i in axn]
                fn.prepared_async_call(grid, block, scomp, cnt, y, beta, *args)

        return AxnpbyKernel()
