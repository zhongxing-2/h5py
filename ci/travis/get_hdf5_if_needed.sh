#!/bin/bash

set -e

if [ -z ${HDF5_DIR+x} ]; then
    echo "Using OS HDF5"
else
    echo "Using downloaded HDF5"
    #python3 -m pip install requests
    #python3 ci/get_hdf5.py
    if [ -f $HDF5_DIR/lib/libhdf5.so ]; then
	echo "using cached build"
    else
        pushd /tmp
        #                             Remove trailing .*, to get e.g. '1.12' ↓
        wget "https://www.hdfgroup.org/ftp/HDF5/releases/hdf5-${HDF5_VERSION%.*}/hdf5-$HDF5_VERSION/src/hdf5-$HDF5_VERSION.tar.gz"
        tar -xzvf hdf5-$HDF5_VERSION.tar.gz
        pushd hdf5-$HDF5_VERSION
        chmod u+x autogen.sh
        ./configure --prefix $HDF5_DIR
        make -j $(nproc)
        make install
        popd
        popd
    fi
fi
