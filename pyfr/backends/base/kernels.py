# -*- coding: utf-8 -*-

from __future__ import absolute_import

from abc import ABCMeta, abstractmethod
import itertools as it
import types

from pyfr.util import memoize, proxylist


class _BaseKernel(object):
    def __call__(self, *args):
        return self, args

    @property
    def retval(self):
        return None

    def run(self, *args, **kwargs):
        pass


class ComputeKernel(_BaseKernel):
    pass


class MPIKernel(_BaseKernel):
    pass


def iscomputekernel(kernel):
    return isinstance(kernel, ComputeKernel)


def ismpikernel(kernel):
    return isinstance(kernel, MPIKernel)


class _MetaKernel(object):
    def __init__(self, kernels):
        self._kernels = proxylist(kernels)

    def run(self, *args, **kwargs):
        self._kernels.run(*args, **kwargs)


class ComputeMetaKernel(_MetaKernel, ComputeKernel):
    pass


class MPIMetaKernel(_MetaKernel, MPIKernel):
    pass


class BaseKernelProvider(object):
    def __init__(self, backend):
        self.backend = backend


class BasePointwiseKernelProvider(BaseKernelProvider):
    __metaclass__ = ABCMeta

    kernel_generator_cls = None
    function_generator_cls = None

    @memoize
    def _render_kernel(self, name, mod, tplargs):
        # Copy the provided argument list
        tplargs = dict(tplargs)

        # Floating point data type used by the backend
        tplargs['fpdtype'] = self.backend.fpdtype

        # Backend-specfic generator classes
        tplargs['_kernel_generator'] = self.kernel_generator_cls
        tplargs['_function_generator'] = self.function_generator_cls

        # Backchannel for obtaining kernel argument types
        tplargs['_kernel_argspecs'] = argspecs = {}

        # Render the template to yield the source code
        tpl = self.backend.lookup.get_template(mod)
        src = tpl.render(**tplargs)

        # Check the kernel exists in the template
        if name not in argspecs:
            raise ValueError('Kernel "{}" not defined in template'
                             .format(name))

        # Extract the metadata for the kernel
        ndim, argn, argt = argspecs[name]

        return src, ndim, argn, argt

    @abstractmethod
    def _build_kernel(self, name, src, args):
        pass

    @abstractmethod
    def _build_arglst(self, dims, argn, argt, argdict):
        pass

    @abstractmethod
    def _instantiate_kernel(self, dims, fun, arglst):
        pass

    def register(self, mod):
        # Derive the name of the kernel from the module
        name = mod[mod.rfind('.') + 1:]

        # See if a kernel has already been registered under this name
        if hasattr(self, name):
            # Same name different module
            if getattr(self, name)._mod != mod:
                raise RuntimeError('Attempt to re-register "{}" with a '
                                   'different module'.format(name))
            # Otherwise (since we're already registered) return
            else:
                return

        # Generate the kernel providing method
        def kernel_meth(self, tplargs, dims, **kwargs):
            # Render the source of kernel
            src, ndim, argn, argt = self._render_kernel(name, mod, tplargs)

            # Compile the kernel
            fun = self._build_kernel(name, src, list(it.chain(*argt)))

            # Process the argument list
            argb = self._build_arglst(dims, argn, argt, kwargs)

            # Return a ComputeKernel subclass instance
            return self._instantiate_kernel(dims, fun, argb)

        # Attach the module to the method as an attribute
        kernel_meth._mod = mod

        # Bind
        setattr(self, name, types.MethodType(kernel_meth, self))
