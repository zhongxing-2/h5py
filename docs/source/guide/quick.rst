.. _quick:

*****************
Quick Start Guide
*****************

This document is a very quick overview of both HDF5 and h5py.  More
comprehensive documentation is available at:

* :ref:`h5pyreference`
* `The h5py FAQ (at Google Code) <http://code.google.com/p/h5py/wiki/FAQ>`_

The `HDF Group <http://www.hdfgroup.org>`_ is the final authority on HDF5.
They also have an `introductory tutorial <http://www.hdfgroup.org/HDF5/Tutor/>`_
which provides a good overview.

What is HDF5?
=============

It's a filesystem for your data.

Only two kinds of objects are stored in HDF5 files: 
*datasets*, which are homogenous, regular arrays of data (just like
NumPy arrays), and *groups*, which are containers that store datasets and
other groups.  Each file is organized using a filesystem metaphor; groups
are like folders, and datasets are like files.  The syntax for accessing
objects in the file is the traditional POSIX filesystem syntax.  Here
are some examples::

    /                       (Root group)
    /MyGroup                (Subgroup)
    /MyGroup/DS1            (Dataset stored in subgroup)
    /MyGroup/Subgroup/DS2   (and so on)

What is h5py?
=============

It's a simple Python interface to HDF5.  You can interact with files, groups
and datasets using traditional Python and NumPy metaphors.  For example,
groups behave like dictionaries, and datasets have shape and dtype attributes,
and can be sliced and indexed just like real NumPy arrays.  Datatypes are
specified using standard NumPy dtype objects.

You don't need to know anything about the HDF5 library to use h5py, apart from
the basic metaphors of files, groups and datasets.  The library handles all
data conversion transparently, and translates operations like slicing into
the appropriate efficient HDF5 routines.

One additional benefit of h5py is that the files it reads and writes are
"plain-vanilla" HDF5 files.  No Python-specific metadata or features are used.
You can read files created by most HDF5 applications, and write files that
any HDF5-aware application can understand.

Getting data into HDF5
======================

First, install h5py by following the :ref:`installation instructions <build>`.

Since an example is worth a thousand words, here's how to make a new file,
and create an integer dataset inside it.  The new dataset has shape (100, 100),
is located in the file at ``"/MyDataset"``, and initialized to the value 42.

    >>> import h5py
    >>> f = h5py.File('myfile.hdf5')
    >>> dset = f.create_dataset("MyDataset", (100, 100), 'i')
    >>> dset[...] = 42

The :ref:`File <hlfile>` constructor accepts modes similar to Python file modes,
including "r", "w", and "a" (the default):

    >>> f = h5py.File('file1.hdf5', 'w')    # overwrite any existing file
    >>> f = h5py.File('file2.hdf5', 'r')    # open read-only

The dataset object ``dset`` here represents a new 2-d HDF5 dataset.  Some
features will be familiar to NumPy users::

    >>> dset.shape
    (100, 100)
    >>> dset.dtype
    dtype('int32')

You can even automatically create a dataset from an existing array:

    >>> import numpy as np
    >>> arr = np.ones((2,3), '=i4')
    >>> dset = f.create_dataset('AnotherDataset', data=arr)

HDF5 datasets support many other features, like chunking and transparent 
compression.  See the section ":ref:`datasets`" for more info.

Getting your data back
----------------------

You can store and retrieve data using Numpy-like slicing syntax.  The following
slice mechanisms are supported:

    * Integers/slices (``array[2:11:3]``, etc)
    * Ellipsis indexing (``array[2,...,4:7]``)
    * Simple broadcasting (``array[2]`` is equivalent to ``array[2,...]``)
    * Index lists (``array[ 2, [0,1,4,6] ]``)

along with some emulated advanced indexing features
(see :ref:`sparse_selection`):

    * Boolean array indexing (``array[ array[...] > 0.5 ]``)
    * Discrete coordinate selection (see the ``selections`` module)

Closing the file
----------------

You don't need to do anything special to "close" datasets.  However, as with
Python files you should close the file before exiting::

    >>> f.close()

H5py tries to close all objects on exit (or when they are no longer referenced),
but it's good practice to close your files anyway.


Groups & multiple objects
=========================

When creating the dataset above, we gave it a name::

    >>> dset.name
    '/MyDataset'

This bears a suspicious resemblance to a POSIX filesystem path; in this case,
we say that MyDataset resides in the *root group* (``/``) of the file.  You
can create other groups as well::

    >>> subgroup = f.create_group("SubGroup")
    >>> subgroup.name
    '/SubGroup'

They can in turn contain new datasets or additional groups::

    >>> dset2 = subgroup.create_dataset('MyOtherDataset', (4,5), '=f8')
    >>> dset2.name
    '/SubGroup/MyOtherDataset'

You can access the contents of groups using dictionary-style syntax, using
POSIX-style paths::

    >>> dset2 = subgroup['MyOtherDataset']
    >>> dset2 = f['/SubGroup/MyOtherDataset']   # equivalent

Groups (including File objects; ``"f"`` in this example) support other
dictionary-like operations::

    >>> list(f)
    ['MyDataset', 'SubGroup']
    >>> 'MyDataset' in f
    True
    >>> 'Subgroup/MyOtherDataset' in f
    True
    >>> del f['MyDataset']

As a safety feature, you can't create an object with a pre-existing name;
you have to manually delete the existing object first::

    >>> grp = f.create_group("NewGroup")
    >>> grp = f.create_group("NewGroup")
    ValueError: Name already exists (Symbol table: Object already exists)
    >>> del f['NewGroup']
    >>> grp = f.create_group("NewGroup")

This restriction reflects HDF5's lack of transactional support, and will not
change.

.. note::

    Most HDF5 versions don't support automatic creation of intermediate
    groups; you can't yet do ``f.create_group('foo/bar/baz')`` unless both
    groups "foo" and "bar" already exist.

Attributes
==========

HDF5 lets you associate small bits of data with both groups and datasets.
This can be used for metadata like descriptive titles or timestamps.

A dictionary-like object which exposes this behavior is attached to every
Group and Dataset object as the attribute ``attrs``.  You can store any scalar
or array value you like::

    >>> dset.attrs
    <Attributes of HDF5 object "MyDataset" (0)>
    >>> dset.attrs["Name"] = "My Dataset"
    >>> dset.attrs["Frob Index"] = 4
    >>> dset.attrs["Order Array"] = numpy.arange(10)
    >>> for name, value in dset.attrs.iteritems():
    ...     print name+":", value
    ...
    Name: My Dataset
    Frob Index: 4
    Order Array: [0 1 2 3 4 5 6 7 8 9]

Attribute proxy objects support the same dictionary-like API as groups, but
unlike group members, you can directly overwrite existing attributes:

    >>> dset.attrs["Name"] = "New Name"

More information
================

Full documentation on files, groups, datasets and attributes is available
in the section ":ref:`h5pyreference`".












