#+
# 
# This file is part of h5py, a low-level Python interface to the HDF5 library.
# 
# Copyright (C) 2008 Andrew Collette
# http://h5py.alfven.org
# License: BSD  (See LICENSE.txt for full license)
# 
# $Date$
# 
#-

import unittest

import h5py
from h5py import h5s, h5i
from h5py.h5 import H5Error

spaces = [(10,10), (1,1), (1,), ()]
max_spaces = [(10,10), (3,4), (h5s.UNLIMITED,), ()]

class TestH5S(unittest.TestCase):


    def test_create_close(self):
        sid = h5s.create(h5s.SCALAR)
        self.assertEqual(h5i.get_type(sid), h5i.DATASPACE)
        sid.close()
        self.assertEqual(h5i.get_type(sid), h5i.BADID)

        self.assertRaises(H5Error, h5s.create, -1)

    def test_copy(self):
        sid = h5s.create(h5s.SCALAR)
        sid2 = sid.copy()
        self.assertEqual(h5i.get_type(sid2), h5i.DATASPACE)

    def test_simple(self):
        # Tests create_simple, get_simple_extent_dims, get_simple_extent_ndims

        for space, max_space in zip(spaces, max_spaces):
            sid = h5s.create_simple(space,max_space)
            self.assertEqual(sid.get_simple_extent_dims(), space)
            self.assertEqual(sid.get_simple_extent_dims(maxdims=True), max_space)
            self.assertEqual(sid.get_simple_extent_ndims(), len(space))

        self.assertRaises(ValueError, h5s.create_simple, None)
        self.assertRaises(H5Error, h5s.create_simple, (10,10), (10,9))
        self.assertRaises(ValueError, h5s.create_simple, (10,10), (10,))

    def test_is_simple(self):
        # According to HDF5 docs, all dataspaces are "simple," even scalar ones.
        sid = h5s.create(h5s.SCALAR)
        self.assert_(sid.is_simple())
        sid = h5s.create(h5s.SIMPLE)    
        self.assert_(sid.is_simple())

    def test_offset_simple(self):
        
        sid = h5s.create_simple((100,100))
        sid.select_hyperslab((0,0), (10,10))
        self.assertEqual(sid.get_select_bounds(), ((0,0),(9,9)))
        sid.offset_simple((2,2))
        self.assertEqual(sid.get_select_bounds(), ((2,2),(11,11)))
        sid.offset_simple(None)
        self.assertEqual(sid.get_select_bounds(), ((0,0),(9,9)))

    def test_get_simple_extent_npoints(self):
        
        sid = h5s.create_simple((100,100))
        self.assertEqual(sid.get_simple_extent_npoints(), 100*100)

    def test_get_simple_extent_type(self):

        sid = h5s.create(h5s.SIMPLE)
        sid2 = h5s.create(h5s.SCALAR)
        self.assertEqual(sid.get_simple_extent_type(), h5s.SIMPLE)
        self.assertEqual(sid2.get_simple_extent_type(), h5s.SCALAR)

    def test_extent_copy(self):

        sid = h5s.create(h5s.SIMPLE)
        sid2 = h5s.create_simple((35,42))
        sid.extent_copy(sid2)
        self.assertEqual(sid.get_simple_extent_dims(), (35,42))

    def test_set_extent_simple(self):

        for space, max_space in zip(spaces, max_spaces):
            sid = h5s.create_simple((10,10))
            sid.set_extent_simple(space, max_space)
            self.assertEqual(sid.get_simple_extent_dims(), space)
            self.assertEqual(sid.get_simple_extent_dims(True), max_space)

    def test_set_extent_none(self):

        sid = h5s.create_simple((10,10))
        sid.set_extent_none()
        self.assertEqual(sid.get_simple_extent_type(), h5s.NO_CLASS)

    def test_get_select_type_npoints(self):

        sid = h5s.create_simple((10,10))
        sid.select_hyperslab((0,0), (5,5))
        self.assertEqual(sid.get_select_type(), h5s.SEL_HYPERSLABS)
        self.assertEqual(sid.get_select_npoints(), 25)

    def test_get_select_bounds(self):

        sid = h5s.create_simple((100,100))
        sid.select_all()
        self.assertEqual(sid.get_select_bounds(), ((0,0), (99,99)))
        sid.select_hyperslab((10,10), (13,17))
        self.assertEqual(sid.get_select_bounds(), ((10,10), (22,26)))

    def test_select(self):
        # all, none, valid

        sid = h5s.create_simple((100,100))
        sid.select_none()
        self.assertEqual(sid.get_select_npoints(), 0)
        sid.select_all()
        self.assertEqual(sid.get_select_npoints(), 100*100)
        sid.select_none()
        self.assertEqual(sid.get_select_npoints(), 0)

        sid.select_hyperslab((0,0), (10,10))
        self.assert_(sid.select_valid())
        sid.select_hyperslab((0,0), (200,200))
        self.assert_(not sid.select_valid())

    def test_elements(self):

        pointlist= [(0,0), (15,98), (4,17), (67,32)] 
        sid = h5s.create_simple((100,100))

        sid.select_elements(pointlist)
        self.assertEqual(sid.get_select_elem_npoints(), len(pointlist))
        self.assertEqual(sid.get_select_elem_pointlist(), pointlist)

    def test_get_blocks(self):

        start = [ (0,0), (50,60) ]
        count = [ (5,5), (13,17) ]

        sid = h5s.create_simple((100,100))
        sid.select_hyperslab(start[0], count[0], op=h5s.SELECT_SET)
        sid.select_hyperslab(start[1], count[1], op=h5s.SELECT_OR)

        self.assertEqual(sid.get_select_hyper_nblocks(), 2)
        blocklist = sid.get_select_hyper_blocklist()
        self.assertEqual(blocklist, [( (0,0), (4,4) ), ( (50,60), (62,76) )])

    def test_py(self):
    
        for space in spaces:
            sid = h5s.create_simple(space)
            self.assertEqual(sid.shape, sid.get_simple_extent_dims())

















