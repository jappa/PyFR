# -*- coding: utf-8 -*-

import numpy as np
import sympy as sy
from sympy.mpmath import mp

from pyfr.bases.base import BaseBasis
from pyfr.quadrules import get_quadrule
from pyfr.syutil import lagrange_basis, nodal_basis
from pyfr.util import lazyprop, memoize


def _orthonormal_basis_tri(order, p, q):
    a, b = 2*(1 + p)/(1 - q) - 1, q

    # Construct an orthonormal basis within a standard triangle
    ob = []
    for i in xrange(order):
        tmp = sy.sqrt(2)*sy.jacobi_normalized(i, 0, 0, a)*(1 - b)**i
        tmp = tmp.ratsimp()

        for j in xrange(order - i):
            poly = sy.expand(tmp*sy.jacobi_normalized(j, 2*i + 1, 0, b))
            ob.append(poly.evalf(mp.dps))

    return ob


def _orthonormal_basis_tet(order, p, q, r):
    a, b, c = 2*(1 + p)/(-q - r) - 1, 2*(1 + q)/(1 - r) - 1, r

    ob = []
    for i in xrange(order):
        tmpi = sy.sqrt(8)*sy.jacobi_normalized(i, 0, 0, a)*(-2*q - 2*r)**i

        for j in xrange(order - i):
            tmpj = sy.jacobi_normalized(j, 2*i + 1, 0, b)*(1 - r)**j
            tmpj = (tmpi*tmpj).ratsimp()

            for k in xrange(order - i - j):
                tmpk = sy.jacobi_normalized(k, 2*(i + j + 1), 0, c)

                ob.append(sy.expand(tmpj*tmpk))

    return ob


class TriBasis(BaseBasis):
    name = 'tri'
    ndims = 2

    # nspts = n*(n + 1)/2
    nspts_coeffs = [1, 1, 0]
    nspts_cdenom = 2

    @classmethod
    def std_ele(cls, sptord):
        pts1d = get_quadrule('line', 'equi-spaced', sptord + 1).points
        sele = [(p, q)
                for i, q in enumerate(pts1d)
                for p in pts1d[:(sptord + 1 - i)]]

        return np.array(sele, dtype=np.object)

    @memoize
    def _orthonormal_basis(self, ptsord):
        return _orthonormal_basis_tri(ptsord, *self._dims)

    @property
    def nupts(self):
        return (self._order + 1)*(self._order + 2) // 2

    @lazyprop
    def ubasis(self):
        return nodal_basis(self.upts,
                           self._orthonormal_basis(self._order + 1),
                           dims=self._dims)

    @lazyprop
    def sbasis(self):
        return nodal_basis(self.spts,
                           self._orthonormal_basis(self._nsptsord),
                           dims=self._dims)

    @lazyprop
    def fpts(self):
        # 1D points
        qrule = self._cfg.get('solver-interfaces-line', 'flux-pts')
        pts1d = np.array(get_quadrule('line', qrule, self._order + 1).points)

        # Project
        proj = [(pts1d, -1), (-pts1d, pts1d), (-1, pts1d)]

        return np.vstack([list(np.broadcast(*p)) for p in proj])

    @property
    def facenorms(self):
        return [(0, -1), (1 / mp.sqrt(2), 1 / mp.sqrt(2)), (-1, 0)]

    @property
    def facefpts(self):
        k = self._order + 1
        return [list(xrange(i*k, (i + 1)*k)) for i in xrange(3)]

    @lazyprop
    def fbasis(self):
        # Dummy parametric symbol
        t = sy.Symbol('_t')

        # Dimension variables
        p, q = self._dims

        # Orthonormal basis
        obasis = self._orthonormal_basis(self._order + 1)

        # Nodal basis along an edge
        qrule = self._cfg.get('solver-interfaces-line', 'flux-pts')
        pts1d = get_quadrule('line', qrule, self._order + 1).points
        nb1d = lagrange_basis(pts1d, t)

        # Allocate space for the flux point basis
        fbasis = np.empty((3, len(nb1d)), dtype=np.object)

        # Parametric mappings (p,q) -> t for the three edges
        # (bottom, hypot, left)
        substs = [{p: t, q: -1}, {p: -t, q: t}, {p: -1, q: t}]

        for i, esub in enumerate(substs):
            for j, lj in enumerate(nb1d):
                fb = sum(sy.integrate(lj*ob.subs(esub), (t, -1, 1))*ob
                         for ob in obasis)
                fbasis[i,j] = fb

        # Account for the longer length of the hypotenuse
        fbasis[1,:] *= mp.sqrt(2)

        return fbasis.ravel()


class TetBasis(BaseBasis):
    name = 'tet'
    ndims = 3

    # nspts = n*(n + 1)*(n + 2)/6
    nspts_coeffs = [1, 3, 2, 0]
    nspts_cdenom = 6

    @classmethod
    def std_ele(cls, sptord):
        pts1d = get_quadrule('line', 'equi-spaced', sptord + 1).points
        sele = [(p, q, r)
                for i, r in enumerate(pts1d)
                for j, q in enumerate(pts1d[:(sptord + 1 - i)])
                for p in pts1d[:(sptord + 1 - i - j)]]

        return np.array(sele, dtype=np.object)

    @memoize
    def _orthonormal_basis(self, ptsord):
        return _orthonormal_basis_tet(ptsord, *self._dims)

    @property
    def nupts(self):
        return (self._order + 1)*(self._order + 2)*(self._order + 3) // 6

    @lazyprop
    def ubasis(self):
        return nodal_basis(self.upts,
                           self._orthonormal_basis(self._order + 1),
                           dims=self._dims)

    @lazyprop
    def sbasis(self):
        return nodal_basis(self.spts,
                           self._orthonormal_basis(self._nsptsord),
                           dims=self._dims)

    @lazyprop
    def fpts(self):
        # 2D points on a triangle
        qrule = self._cfg.get('solver-interfaces-tri', 'flux-pts')
        npts2d = (self._order + 1)*(self._order + 2) // 2

        s, t = np.array(get_quadrule('tri', qrule, npts2d).points).T

        # Project
        proj = [(s, t, -1), (s, -1, t), (-1, t, s), (s, t, -s -t -1)]

        return np.vstack([list(np.broadcast(*p)) for p in proj])

    @property
    def facenorms(self):
        c = 1 / mp.sqrt(3)
        return [(0, 0, -1), (0, -1, 0), (-1, 0, 0), (c, c, c)]

    @property
    def facefpts(self):
        n = (self._order + 1)*(self._order + 2) // 2
        return [list(xrange(i*n, (i + 1)*n)) for i in xrange(4)]

    @lazyprop
    def fbasis(self):
        k = self._order + 1

        # Dummy parametric symbols
        s, t = sy.symbols('_s _t')

        # Dimension variables
        p, q, r = self._dims

        # Orthonormal bases inside of a tetrahedron and triangle
        obtet = self._orthonormal_basis(k)
        obtri = _orthonormal_basis_tri(k, s, t)

        # Flux points inside of a (triangular) face
        qrule = self._cfg.get('solver-interfaces-tri', 'flux-pts')
        ptstri = get_quadrule('tri', qrule, k*(k + 1) // 2).points

        # Obtain a nodal basis inside of this triangular face
        nbtri = nodal_basis(ptstri, obtri, dims=(s, t))

        # Allocate space for the flux point basis
        fbasis = np.empty((4, len(nbtri)), dtype=np.object)

        # Parametric mappings for the four faces
        substs = [
            {p: s, q: t, r: -1},
            {p: s, q: -1, r: t},
            {p: -1, q: t, r: s},
            {p: s, q: t, r: -s -t - 1}
        ]

        for i, esub in enumerate(substs):
            for j, lj in enumerate(nbtri):
                fb = sum(sy.integrate(lj*ob.subs(esub),
                                      (s, -1, -t), (t, -1, 1))*ob
                         for ob in obtet)
                fbasis[i,j] = fb

        # Account for different area of the centre face
        fbasis[3,:] *= mp.sqrt(3)

        return fbasis.ravel()
