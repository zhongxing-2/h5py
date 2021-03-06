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

from defs_c cimport size_t
from h5 cimport hid_t, herr_t, haddr_t
from h5g cimport H5G_obj_t

cdef extern from "hdf5.h":

  size_t H5R_DSET_REG_REF_BUF_SIZE
  size_t H5R_OBJ_REF_BUF_SIZE

  ctypedef enum H5R_type_t:
    H5R_BADTYPE = (-1),
    H5R_OBJECT,
    H5R_DATASET_REGION,
    H5R_INTERNAL,
    H5R_MAXTYPE

  ctypedef haddr_t hobj_ref_t
  ctypedef unsigned char hdset_reg_ref_t[12]

  herr_t    H5Rcreate(void *ref, hid_t loc_id, char *name, H5R_type_t ref_type, 
                      hid_t space_id) except *
  hid_t     H5Rdereference(hid_t obj_id, H5R_type_t ref_type, void *ref) except *
  hid_t     H5Rget_region(hid_t dataset, H5R_type_t ref_type, void *ref) except *
  H5G_obj_t H5Rget_obj_type(hid_t id, H5R_type_t ref_type, void *ref) except *


