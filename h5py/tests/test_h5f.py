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

import numpy
import os
import tempfile
from common import TestBase

from h5py import *
from h5py.h5 import H5Error

HDFNAME = 'attributes.hdf5'

class TestH5F(TestBase):

    HDFNAME = HDFNAME

    def test_open_close(self):
        fid = h5f.open(self.HDFNAME, h5f.ACC_RDONLY)
        self.assertEqual(h5i.get_type(fid), h5i.FILE)
        fid.close()
        self.assertEqual(h5i.get_type(fid), h5i.BADID)

        self.assertRaises(H5Error, h5f.open, 'SOME OTHER NAME')

    def test_create(self):
        name = tempfile.mktemp('.hdf5')
        fid = h5f.create(name)
        try:
            self.assertEqual(h5i.get_type(fid), h5i.FILE)
            fid.close()
            self.assertRaises(H5Error, h5f.create, name, h5f.ACC_EXCL)
        finally:
            try:
                os.unlink(name)
            except OSError:
                pass

    def test_flush(self):
        h5f.flush(self.fid)

    def test_is_hdf5(self):
        fd, name = tempfile.mkstemp('.hdf5')
        os.close(fd)
        try:
            self.assert_(not h5f.is_hdf5(name))
        finally:
            try:
                os.unlink(name)
            except OSError:
                pass

        self.assert_(h5f.is_hdf5(self.fname))

    def test_get_filesize(self):
        self.assertEqual(self.fid.get_filesize(), os.stat(self.fname).st_size)

    def test_get_create_plist(self):
        cplist = self.fid.get_create_plist()
        self.assert_(cplist.get_class().equal(h5p.FILE_CREATE))

    def test_get_access_plist(self):
        aplist = self.fid.get_access_plist()
        self.assert_(aplist.get_class().equal(h5p.FILE_ACCESS))

    def test_get_freespace(self):
        self.assert_(self.fid.get_freespace() >= 0)

    def test_get_name(self):
        self.assertEqual(h5f.get_name(self.fid), self.fname)

    def test_get_obj_count(self):
        self.assert_(h5f.get_obj_count(self.fid, h5f.OBJ_ALL) >= 0)
        self.assertRaises(H5Error, h5f.get_obj_count, -1, h5f.OBJ_ALL)
    
    def test_get_obj_ids(self):
        idlist = h5f.get_obj_ids(self.fid, h5f.OBJ_ALL)
        self.assert_(isinstance(idlist, list))
        self.assertRaises(H5Error, h5f.get_obj_ids, -1, h5f.OBJ_ALL)

    def test_py(self):
        self.assertEqual(self.fid.name, self.fname)



    
        
