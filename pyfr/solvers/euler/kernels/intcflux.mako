# -*- coding: utf-8 -*-
<%inherit file='base'/>
<%namespace module='pyfr.backends.base.makoutil' name='pyfr'/>

<%include file='pyfr.solvers.euler.kernels.rsolvers.${rsolver}'/>

<%pyfr:kernel name='intcflux' ndim='1'
              ul='inout view fpdtype_t[${str(nvars)}]'
              ur='inout view fpdtype_t[${str(nvars)}]'
              nl='in fpdtype_t[${str(ndims)}]'
              magnl='in fpdtype_t'
              magnr='in fpdtype_t'>
    // Perform the Riemann solve
    fpdtype_t fn[${nvars}];
    rsolve(ul, ur, nl, fn);

    // Scale and write out the common normal fluxes
% for i in range(nvars):
    ul[${i}] =  magnl*fn[${i}];
    ur[${i}] = -magnr*fn[${i}];
% endfor
</%pyfr:kernel>
