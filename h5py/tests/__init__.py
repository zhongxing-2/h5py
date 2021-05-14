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
import sys
import test_h5a, test_h5d, test_h5f, \
       test_h5g, test_h5i, test_h5p, \
       test_h5s, test_h5t, test_h5, \
       test_highlevel

from h5py import *

TEST_CASES = (test_h5a.TestH5A, test_h5d.TestH5D, test_h5f.TestH5F, 
              test_h5g.TestH5G, test_h5i.TestH5I, test_h5p.TestH5P,
              test_h5s.TestH5S, test_h5t.TestH5T, test_h5.TestH5,
              test_highlevel.TestFile, test_highlevel.TestDataset,
              test_highlevel.TestGroup)

def buildsuite(cases):

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for test_case in cases:
        suite.addTests(loader.loadTestsFromTestCase(test_case))
    return suite

def runtests():
    suite = buildsuite(TEST_CASES)
    retval = unittest.TextTestRunner(verbosity=3).run(suite)
    print "=== Tested HDF5 %s (%s API) ===" % (h5.hdf5_version, h5.api_version)
    return retval.wasSuccessful()

def autotest():
    if not runtests():
        sys.exit(1)



