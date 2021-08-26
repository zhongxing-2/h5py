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

include "defs.pxd"

from h5 cimport class ObjectID

cdef class FileID(ObjectID):
    pass

# Internal h5py function to wrap file-resident identifiers
# TODO: move this to h5i
cdef object wrap_identifier(hid_t ident)


