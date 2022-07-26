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

"""
    Provides high-level Python objects for HDF5 files, groups, and datasets.  

    Objects in this module are designed to provide a friendly, Python-style
    interface to native HDF5 concepts like files, datasets, groups and
    attributes.  The module is written in pure Python and uses the standard
    h5py low-level interface exclusively.

    Most components defined here are re-exported into the root h5py package
    namespace, because they are the most straightforward and intuitive
    way to interact with HDF5.
"""

from __future__ import with_statement

import os
import numpy
import threading
import sys

import os.path as op
import posixpath as pp

from h5py import h5, h5f, h5g, h5s, h5t, h5d, h5a, h5p, h5z, h5i, h5fd
from h5py.h5 import H5Error
import h5py.selections as sel
from h5py.selections import CoordsList

import filters

config = h5.get_config()
if config.API_18:
    from h5py import h5o, h5l

__all__ = ["File", "Group", "Dataset",
           "Datatype", "AttributeManager"]

def _hbasename(name):
    """ Basename function with more readable handling of trailing slashes"""
    name = pp.basename(pp.normpath(name))
    return name if name != '' else '/'

def is_hdf5(fname):
    """ Determine if a file is valid HDF5 (False if it doesn't exist). """
    fname = os.path.abspath(fname)
    if os.path.isfile(fname):
        try:
            return h5f.is_hdf5(fname)
        except H5Error:
            pass
    return False

# === Base classes ============================================================

class _LockableObject(object):

    """
        Base class which provides rudimentary locking support.
    """

    _lock = threading.RLock()


class HLObject(_LockableObject):

    """
        Base class for high-level interface objects.

        All objects of this class support the following properties:

        id:     Low-level identifer, compatible with the h5py.h5* modules.
        name:   Name of this object in the HDF5 file.  May not be unique.
        attrs:  HDF5 attributes of this object.  See AttributeManager class.

        Equality comparison and hashing are based on native HDF5 object
        identity.
    """

    @property
    def name(self):
        """Name of this object in the HDF5 file.  Not necessarily unique."""
        return h5i.get_name(self.id)

    @property
    def attrs(self):
        """Provides access to HDF5 attributes. See AttributeManager."""
        return self._attrs

    @property
    def file(self):
        """Return the File instance associated with this object"""
        if isinstance(self, File):
            return self
        else:
            return self._file

    @property
    def parent(self):
        """Return the parent group of this object.

        Beware; if multiple hard links to this object exist, there's no way
        to predict which parent group will be returned!
        """
        return self.file[pp.dirname(self.name)]

    def __init__(self, parent):
        if not isinstance(self, File):
            if isinstance(parent, File):
                self._file = parent
            else:
                self._file = parent._file

    def __nonzero__(self):
        return self.id.__nonzero__()

    def __hash__(self):
        return hash(self.id)
    def __eq__(self, other):
        if hasattr(other, 'id'):
            return self.id == other.id
        return False

class _DictCompat(object):

    """
        Contains dictionary-style compatibility methods for groups and
        attributes.
    """
    
    def keys(self):
        """ Get a list containing member names """
        with self._lock:
            return list(self)

    def iterkeys(self):
        """ Get an iterator over member names """
        with self._lock:
            return iter(self)

    def values(self):
        """ Get a list containing member objects """
        with self._lock:
            return [self[x] for x in self]

    def itervalues(self):
        """ Get an iterator over member objects """
        with self._lock:
            for x in self:
                yield self[x]

    def items(self):
        """ Get a list of tuples containing (name, object) pairs """
        with self._lock:
            return [(x, self[x]) for x in self]

    def iteritems(self):
        """ Get an iterator over (name, object) pairs """
        with self._lock:
            for x in self:
                yield (x, self[x])

    def get(self, name, default):
        """ Retrieve the member, or return default if it doesn't exist """
        with self._lock:
            if name in self:
                return self[name]
            return default

    # Compatibility methods
    def listnames(self):
        """ Deprecated alias for keys() """
        return self.keys()
    def iternames(self):
        """ Deprecated alias for iterkeys() """
        return self.iterkeys()
    def listobjects(self):
        """ Deprecated alias for values() """
        return self.values()
    def iterobjects(self):
        """ Deprecated alias for itervalues() """
        return self.itervalues()
    def listitems(self):
        """ Deprecated alias for items() """
        return self.items()

class Group(HLObject, _DictCompat):

    """ Represents an HDF5 group.

        It's recommended to use the Group/File method create_group to create
        these objects, rather than trying to create them yourself.

        Groups implement a basic dictionary-style interface, supporting
        __getitem__, __setitem__, __len__, __contains__, keys(), values()
        and others.

        They also contain the necessary methods for creating new groups and
        datasets.  Group attributes can be accessed via <group>.attrs.
    """

    def __init__(self, parent_object, name, create=False):
        """ Create a new Group object, from a parent object and a name.

        If "create" is False (default), try to open the given group,
        raising an exception if it doesn't exist.  If "create" is True,
        create a new HDF5 group and link it into the parent group.

        It's recommended to use __getitem__ or create_group() rather than
        calling the constructor directly.
        """
        with parent_object._lock:
            HLObject.__init__(self, parent_object)
            if create:
                self.id = h5g.create(parent_object.id, name)
            else:
                self.id = h5g.open(parent_object.id, name)

            self._attrs = AttributeManager(self)
    
    def __setitem__(self, name, obj):
        """ Add an object to the group.  The name must not already be in use.

        The action taken depends on the type of object assigned:

        1. Named HDF5 object (Dataset, Group, Datatype):
            A hard link is created in this group which points to the
            given object.

        2. Numpy ndarray:
            The array is converted to a dataset object, with default
            settings (contiguous storage, etc.).

        3. Numpy dtype:
            Commit a copy of the datatype as a named datatype in the file.

        4. Anything else:
            Attempt to convert it to an ndarray and store it.  Scalar
            values are stored as scalar datasets. Raise ValueError if we
            can't understand the resulting array dtype.
        """
        with self._lock:
            if isinstance(obj, Group) or isinstance(obj, Dataset) or isinstance(obj, Datatype):
                self.id.link(h5i.get_name(obj.id), name, link_type=h5g.LINK_HARD)

            elif isinstance(obj, numpy.dtype):
                htype = h5t.py_create(obj)
                htype.commit(self.id, name)

            else:
                self.create_dataset(name, data=obj)

    def __getitem__(self, name):
        """ Open an object attached to this group. 
        """
        with self._lock:
            info = h5g.get_objinfo(self.id, name)

            if info.type == h5g.DATASET:
                return Dataset(self, name)

            elif info.type == h5g.GROUP:
                return Group(self, name)

            elif info.type == h5g.TYPE:
                return Datatype(self, name)

            raise ValueError("Don't know how to open object of type %d" % info.type)

    def __delitem__(self, name):
        """ Delete (unlink) an item from this group. """
        self.id.unlink(name)

    # TODO: this fails with > 2**32 entries
    def __len__(self):
        """ Number of members attached to this group """
        return self.id.get_num_objs()

    def __contains__(self, name):
        """ Test if a member name exists """
        return name in self.id

    def __iter__(self):
        """ Iterate over member names """
        return self.id.__iter__()

    def create_group(self, name):
        """ Create and return a subgroup. Fails if the group already exists.
        """
        return Group(self, name, create=True)

    def require_group(self, name):
        """ Check if a group exists, and create it if not.  TypeError if an
        incompatible object exists.
        """
        if not name in self:
            return self.create_group(name)
        else:
            grp = self[name]
            if not isinstance(grp, Group):
                raise TypeError("Incompatible object (%s) already exists" % grp.__class__.__name__)
            return grp

    def create_dataset(self, name, *args, **kwds):
        """ Create and return a new dataset.  Fails if "name" already exists.

        create_dataset(name, shape, [dtype=<Numpy dtype>], **kwds)
        create_dataset(name, data=<Numpy array>, **kwds)

        The default dtype is '=f4' (single-precision float).

        Additional keywords ("*" is default):

        chunks
            Tuple of chunk dimensions or None*

        maxshape
            None* or a tuple giving maximum dataset size.  An element of None
            indicates an unlimited dimension.  Dataset can be expanded by
            calling resize()

        compression
            Compression strategy; None*, 'gzip', 'szip' or 'lzf'.  An integer
            is interpreted as a gzip level.

        compression_opts
            Optional compression settings; for gzip, this may be an int.  For
            szip, it should be a 2-tuple ('ec'|'nn', int(0-32)).   

        shuffle
            Use the shuffle filter (increases compression performance for
            gzip and LZF).  True/False*.

        fletcher32
            Enable error-detection.  True/False*.
        """
        return Dataset(self, name, *args, **kwds)

    def require_dataset(self, name, shape, dtype, exact=False, **kwds):
        """Open a dataset, or create it if it doesn't exist.

        Checks if a dataset with compatible shape and dtype exists, and
        creates one if it doesn't.  Raises TypeError if an incompatible
        dataset (or group) already exists.  

        By default, datatypes are compared for loss-of-precision only.
        To require an exact match, set keyword "exact" to True.  Shapes
        are always compared exactly.

        Keyword arguments are only used when creating a new dataset; they
        are ignored if an dataset with matching shape and dtype already
        exists.  See create_dataset for a list of legal keywords.
        """
        dtype = numpy.dtype(dtype)

        with self._lock:
            if not name in self:
                return self.create_dataset(name, *(shape, dtype), **kwds)

            dset = self[name]
            if not isinstance(dset, Dataset):
                raise TypeError("Incompatible object (%s) already exists" % dset.__class__.__name__)

            if not shape == dset.shape:
                raise TypeError("Shapes do not match (existing %s vs new %s)" % (dset.shape, shape))

            if exact:
                if not dtype == dset.dtype:
                    raise TypeError("Datatypes do not exactly match (existing %s vs new %s)" % (dset.dtype, dtype))
            elif not numpy.can_cast(dtype, dset.dtype):
                raise TypeError("Datatypes cannot be safely cast (existing %s vs new %s)" % (dset.dtype, dtype))
            
            return dset

    # New 1.8.X methods

    def copy(self, source, dest, name=None):
        """ Copy an object or group (Requires HDF5 1.8).

        The source can be a path, Group, Dataset, or Datatype object.  The
        destination can be either a path or a Group object.  The source and
        destinations need not be in the same file.

        When the destination is a Group object, by default the target will
        be created in that group with its current name (basename of obj.name).
        You can override that by setting "name" to a string.

        Example:

        >>> f = File('myfile.hdf5')
        >>> f.listnames()
        ['MyGroup']
        >>> f.copy('MyGroup', 'MyCopy')
        >>> f.listnames()
        ['MyGroup', 'MyCopy']

        """
        if not config.API_18:
            raise NotImplementedError("This feature is only available with HDF5 1.8.0 and later")

        with self._lock:

            if isinstance(source, HLObject):
                source_path = '.'
            else:
                # Interpret source as a path relative to this group
                source_path = source
                source = self

            if isinstance(dest, Group):
                if name is not None:
                    dest_path = name
                else:
                    dest_path = pp.basename(h5i.get_name(source[source_path].id))

            elif isinstance(dest, HLObject):
                raise TypeError("Destination must be path or Group object")
            else:
                # Interpret destination as a path relative to this group
                dest_path = dest
                dest = self

            h5o.copy(source.id, source_path, dest.id, dest_path)

    def visit(self, func):
        """ Recursively visit all names in this group and subgroups (HDF5 1.8).

        You supply a callable (function, method or callable object); it
        will be called exactly once for each link in this group and every
        group below it. Your callable must conform to the signature:

            func(<member name>) => <None or return value>

        Returning None continues iteration, returning anything else stops
        and immediately returns that value from the visit method.  No
        particular order of iteration within groups is guranteed.

        Example:

        >>> # List the entire contents of the file
        >>> f = File("foo.hdf5")
        >>> list_of_names = []
        >>> f.visit(list_of_names.append)
        """
        if not config.API_18:
            raise NotImplementedError("This feature is only available with HDF5 1.8.0 and later")
    
        with self._lock:
            return h5o.visit(self.id, func)

    def visititems(self, func):
        """ Recursively visit names and objects in this group (HDF5 1.8).

        You supply a callable (function, method or callable object); it
        will be called exactly once for each link in this group and every
        group below it. Your callable must conform to the signature:

            func(<member name>, <object>) => <None or return value>

        Returning None continues iteration, returning anything else stops
        and immediately returns that value from the visit method.  No
        particular order of iteration within groups is guranteed.

        Example:

        # Get a list of all datasets in the file
        >>> mylist = []
        >>> def func(name, obj):
        ...     if isinstance(obj, Dataset):
        ...         mylist.append(name)
        ...
        >>> f = File('foo.hdf5')
        >>> f.visititems(func)
        """
        if not config.API_18:
            raise NotImplementedError("This feature is only available with HDF5 1.8.0 and later")

        with self._lock:
            def call_proxy(name):
                return func(name, self[name])
            return h5o.visit(self.id, call_proxy)

    def __repr__(self):
        with self._lock:
            try:
                return '<HDF5 group "%s" (%d members)>' % \
                    (_hbasename(self.name), len(self))
            except Exception:
                return "<Closed HDF5 group>"

class File(Group):

    """ Represents an HDF5 file on disk.

        File(name, mode=None, driver=None, **driver_kwds)

        Legal modes: r, r+, w, w-, a (default)

        File objects inherit from Group objects; Group-like methods all
        operate on the HDF5 root group ('/').  Like Python file objects, you
        must close the file ("obj.close()") when you're done with it. File
        objects may also be used as context managers in Python "with" blocks.

        The HDF5 file driver may also be specified:

        None
            Use the standard HDF5 driver appropriate for the current platform.
            On UNIX, this is the H5FD_SEC2 driver; on Windows, it is
            H5FD_WINDOWS.

        'sec2'
            Unbuffered, optimized I/O using standard POSIX functions.

        'stdio' 
            Buffered I/O using functions from stdio.h.

        'core'
            Memory-map the entire file; all operations are performed in
            memory and written back out when the file is closed.  Keywords:

            backing_store:  If True (default), save changes to a real file
                            when closing.  If False, the file exists purely
                            in memory and is discarded when closed.

            block_size:     Increment (in bytes) by which memory is extended.
                            Default is 1 megabyte (1024**2).

        'family'
            Store the file on disk as a series of fixed-length chunks.  Useful
            if the file system doesn't allow large files.  Note: the filename
            you provide *must* contain the string "%d", which will be replaced
            by the file sequence number.  Keywords:

            memb_size:  Maximum file size (default is 2**31-1).
    """

    @property
    def filename(self):
        """File name on disk"""
        return h5f.get_name(self.fid)

    @property
    def mode(self):
        """Python mode used to open file"""
        return self._mode

    @property
    def driver(self):
        """Low-level HDF5 file driver used to open file"""
        drivers = {h5fd.SEC2: 'sec2', h5fd.STDIO: 'stdio',
                   h5fd.CORE: 'core', h5fd.FAMILY: 'family',
                   h5fd.WINDOWS: 'windows'}
        return drivers.get(self.fid.get_access_plist().get_driver(), 'unknown')

    # --- Public interface (File) ---------------------------------------------

    def __init__(self, name, mode=None, driver=None, **driver_kwds):
        """ Create a new file object.  

        Valid modes (like Python's file() modes) are: 
        - r   Readonly, file must exist
        - r+  Read/write, file must exist
        - w   Create file, truncate if exists
        - w-  Create file, fail if exists
        - a   Read/write if exists, create otherwise (default)

        Valid drivers are:
        - None      Use default driver ('sec2' on UNIX, 'windows' on Win32) 
        - 'sec2'    Standard UNIX driver
        - 'stdio'   Stdio (buffered) driver
        - 'core'    mmap driver
        - 'family'  Multi-part file driver
        """
        plist = h5p.create(h5p.FILE_ACCESS)
        plist.set_fclose_degree(h5f.CLOSE_STRONG)
        if driver is not None and not (driver=='windows' and sys.platform=='win32'):
            if(driver=='sec2'):
                plist.set_fapl_sec2(**driver_kwds)
            elif(driver=='stdio'):
                plist.set_fapl_stdio(**driver_kwds)
            elif(driver=='core'):
                plist.set_fapl_core(**driver_kwds)
            elif(driver=='family'):
                plist.set_fapl_family(memb_fapl=plist.copy(), **driver_kwds)
            else:
                raise ValueError('Unknown driver type "%s"' % driver)

        if mode == 'r':
            self.fid = h5f.open(name, h5f.ACC_RDONLY, fapl=plist)
        elif mode == 'r+':
            self.fid = h5f.open(name, h5f.ACC_RDWR, fapl=plist)
        elif mode == 'w-':
            self.fid = h5f.create(name, h5f.ACC_EXCL, fapl=plist)
        elif mode == 'w':
            self.fid = h5f.create(name, h5f.ACC_TRUNC, fapl=plist)
        elif mode == 'a' or mode is None:
            if not os.path.exists(name):
                self.fid = h5f.create(name, h5f.ACC_EXCL, fapl=plist)
            else:
                self.fid = h5f.open(name, h5f.ACC_RDWR, fapl=plist)
        else:
            raise ValueError("Invalid mode; must be one of r, r+, w, w-, a")

        self.id = self.fid  # So the Group constructor can find it.
        Group.__init__(self, self, '/')

        self._mode = mode

    def close(self):
        """ Close this HDF5 file.  All open objects will be invalidated.
        """
        with self._lock:
            self.id._close()
            self.fid.close()

    def flush(self):
        """ Tell the HDF5 library to flush its buffers.
        """
        h5f.flush(self.fid)

    def __enter__(self):
        return self

    def __exit__(self,*args):
        with self._lock:
            if self.id._valid:
                self.close()
            
    def __repr__(self):
        with self._lock:
            try:
                return '<HDF5 file "%s" (mode %s, %d root members)>' % \
                    (os.path.basename(self.name), self.mode, len(self))
            except Exception:
                return "<Closed HDF5 file>"

    # Fix up identity to use the file identifier, not the root group.
    def __hash__(self):
        return hash(self.fid)
    def __eq__(self, other):
        if hasattr(other, 'fid'):
            return self.fid == other.fid
        return False

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

class Dataset(HLObject):

    """ High-level interface to an HDF5 dataset.

        Datasets can be opened via the syntax Group[<dataset name>], and
        created with the method Group.create_dataset().

        Datasets behave superficially like Numpy arrays.  NumPy "simple"
        slicing is fully supported, along with a subset of fancy indexing
        and indexing by field names (dataset[0:10, "fieldname"]).

        The standard NumPy properties "shape" and "dtype" are also available.
    """

    def _g_shape(self):
        """Numpy-style shape tuple giving dataset dimensions"""
        return self.id.shape

    def _s_shape(self, shape):
        self.resize(shape)

    shape = property(_g_shape, _s_shape)

    @property
    def dtype(self):
        """Numpy dtype representing the datatype"""
        return self.id.dtype

    @property
    def value(self):
        """  Deprecated alias for dataset[...] and dataset[()] """
        with self._lock:
            arr = self[...]
            #if arr.shape == ():
            #    return numpy.asscalar(arr)
            return arr

    @property
    def chunks(self):
        """Dataset chunks (or None)"""
        return self._chunks

    @property
    def compression(self):
        """Compression strategy (or None)"""
        for x in ('gzip','lzf','szip'):
            if x in self._filters:
                return x
        return None

    @property
    def compression_opts(self):
        """ Compression setting.  Int(0-9) for gzip, 2-tuple for szip. """
        return self._filters.get(self.compression, None)

    @property
    def shuffle(self):
        """Shuffle filter present (T/F)"""
        return 'shuffle' in self._filters

    @property
    def fletcher32(self):
        """Fletcher32 filter is present (T/F)"""
        return 'fletcher32' in self._filters
        
    @property
    def maxshape(self):
        space = self.id.get_space()
        dims = space.get_simple_extent_dims(True)
        return tuple(x if x != h5s.UNLIMITED else None for x in dims)

    def __init__(self, group, name,
                    shape=None, dtype=None, data=None,
                    chunks=None, compression=None, shuffle=None,
                    fletcher32=None, maxshape=None, compression_opts=None):
        """ Open or create a new dataset in the file.

        It's recommended you use the Group methods (open via Group["name"],
        create via Group.create_dataset), rather than calling the constructor.

        There are two modes of operation for this constructor:

        1.  Open an existing dataset:
              Dataset(group, name)

        2.  Create a dataset:
              Dataset(group, name, shape, [dtype=<Numpy dtype>], **kwds)
            or
              Dataset(group, name, data=<Numpy array>, **kwds)

              If "dtype" is not specified, the default is single-precision
              floating point, with native byte order ("=f4").

        Creating a dataset will fail if another of the same name already 
        exists.  Also, chunks/compression/shuffle/fletcher32 may only be
        specified when creating a dataset.

        Creation keywords (* is default):

        chunks:        Tuple of chunk dimensions, True, or None*
        compression:   "gzip", "lzf", or "szip" (if available)
        shuffle:       Use the shuffle filter? (requires compression) T/F*
        fletcher32:    Enable Fletcher32 error detection? T/F*
        maxshape:      Tuple giving dataset maximum dimensions or None*.
                       You can grow each axis up to this limit using
                       resize().  For each unlimited axis, provide None.
        
        compress_opts: Optional setting for the compression filter

        All these options require chunking.  If a chunk tuple is not
        provided, the constructor will guess an appropriate chunk shape.
        Please note none of these are allowed for scalar datasets.
        """
        with group._lock:
            HLObject.__init__(self, group)
            if data is None and shape is None:
                if any((dtype,chunks,compression,shuffle,fletcher32)):
                    raise ValueError('You cannot specify keywords when opening a dataset.')
                self.id = h5d.open(group.id, name)
            else:
                
                # Convert data to a C-contiguous ndarray
                if data is not None:
                    data = numpy.asarray(data, order="C")

                # Validate shape
                if shape is None:
                    if data is None:
                        raise TypeError("Either data or shape must be specified")
                    shape = data.shape
                else:
                    shape = tuple(shape)
                    if data is not None and (numpy.product(shape) != numpy.product(data.shape)):
                        raise ValueError("Shape tuple is incompatible with data")

                # Validate dtype
                if dtype is None and data is None:
                    dtype = numpy.dtype("=f4")
                elif dtype is None and data is not None:
                    dtype = data.dtype
                else:
                    dtype = numpy.dtype(dtype)

                # Legacy
                if any((compression, shuffle, fletcher32, maxshape)):
                    if chunks is False:
                        raise ValueError("Chunked format required for given storage options")

                # Legacy
                if compression in range(10) or compression is True:
                    if compression_opts is None:
                        if compression is True:
                            compression_opts = 4
                        else:
                            compression_opts = compression
                    else:
                        raise TypeError("Conflict in compression options")
                    compression = 'gzip'

                # Generate the dataset creation property list
                # This also validates the keyword arguments
                plist = filters.generate_dcpl(shape, dtype, chunks, compression,
                            compression_opts, shuffle, fletcher32, maxshape)

                if maxshape is not None:
                    maxshape = tuple(x if x is not None else h5s.UNLIMITED for x in maxshape)

                space_id = h5s.create_simple(shape, maxshape)
                type_id = h5t.py_create(dtype, logical=True)

                self.id = h5d.create(group.id, name, type_id, space_id, plist)
                if data is not None:
                    self.id.write(h5s.ALL, h5s.ALL, data)

            self._attrs = AttributeManager(self)
            plist = self.id.get_create_plist()
            self._filters = filters.get_filters(plist)
            if plist.get_layout() == h5d.CHUNKED:
                self._chunks = plist.get_chunk()
            else:
                self._chunks = None

    def resize(self, size, axis=None):
        """ Resize the dataset, or the specified axis (HDF5 1.8 only).

        The dataset must be stored in chunked format; it can be resized up to
        the "maximum shape" (keyword maxshape) specified at creation time.
        The rank of the dataset cannot be changed.

        "Size" should be a shape tuple, or if an axis is specified, an integer.

        BEWARE: This functions differently than the NumPy resize() method!
        The data is not "reshuffled" to fit in the new shape; each axis is
        grown or shrunk independently.  The coordinates of existing data is
        fixed.
        """
        with self._lock:

            if not config.API_18:
                raise NotImplementedError("Resizing is only available with HDF5 1.8.")

            if self.chunks is None:
                raise TypeError("Only chunked datasets can be resized")

            if axis is not None:
                if not axis >=0 and axis < self.id.rank:
                    raise ValueError("Invalid axis (0 to %s allowed)" % self.id.rank-1)
                try:
                    newlen = int(size)
                except TypeError:
                    raise TypeError("Argument must be a single int if axis is specified")
                size = list(self.shape)
                size[axis] = newlen

            size = tuple(size)
            self.id.set_extent(size)
            h5f.flush(self.id)  # THG recommends
            
    def __len__(self):
        """ The size of the first axis.  TypeError if scalar.

        Limited to 2**32 on 32-bit systems; Dataset.len() is preferred.
        """
        size = self.len()
        if size > sys.maxint:
            raise OverflowError("Value too big for Python's __len__; use Dataset.len() instead.")
        return size

    def len(self):
        """ The size of the first axis.  TypeError if scalar. 

        Use of this method is preferred to len(dset), as Python's built-in
        len() cannot handle values greater then 2**32 on 32-bit systems.
        """
        shape = self.shape
        if len(shape) == 0:
            raise TypeError("Attempt to take len() of scalar dataset")
        return shape[0]

    def __iter__(self):
        """ Iterate over the first axis.  TypeError if scalar.

        BEWARE: Modifications to the yielded data are *NOT* written to file.
        """
        shape = self.shape
        if len(shape) == 0:
            raise TypeError("Can't iterate over a scalar dataset")
        for i in xrange(shape[0]):
            yield self[i]

    def __getitem__(self, args):
        """ Read a slice from the HDF5 dataset.

        Takes slices and recarray-style field names (more than one is
        allowed!) in any order.  Obeys basic NumPy rules, including
        broadcasting.

        Also supports:

        * Boolean "mask" array indexing
        * Advanced dataspace selection via the "selections" module
        """
        with self._lock:

            args = args if isinstance(args, tuple) else (args,)

            # Sort field indices from the rest of the args.
            names = tuple(x for x in args if isinstance(x, str))
            args = tuple(x for x in args if not isinstance(x, str))

            # Create NumPy datatype for read, using only the named fields
            # as specified by the user.
            basetype = self.id.dtype
            if len(names) == 0:
                new_dtype = basetype
            else:
                for name in names:
                    if not name in basetype.names:
                        raise ValueError("Field %s does not appear in this type." % name)
                new_dtype = numpy.dtype([(name, basetype.fields[name][0]) for name in names])

            # Perform the dataspace selection.
            selection = sel.select(self.shape, args)

            if selection.nselect == 0:
                return numpy.ndarray((0,), dtype=new_dtype)

            # Create the output array using information from the selection.
            arr = numpy.ndarray(selection.mshape, new_dtype, order='C')

            # This is necessary because in the case of array types, NumPy
            # discards the array information at the top level.
            mtype = h5t.py_create(new_dtype)

            # Perfom the actual read
            mspace = h5s.create_simple(selection.mshape)
            fspace = selection._id
            self.id.read(mspace, fspace, arr, mtype)

            # Patch up the output for NumPy
            if len(names) == 1:
                arr = arr[names[0]]     # Single-field recarray convention
            if arr.shape == ():
                arr = numpy.asscalar(arr)
            return arr

    def __setitem__(self, args, val):
        """ Write to the HDF5 dataset from a Numpy array.

        NumPy's broadcasting rules are honored, for "simple" indexing
        (slices and integers).  For advanced indexing, the shapes must
        match.

        Classes from the "selections" module may also be used to index.
        """
        with self._lock:

            args = args if isinstance(args, tuple) else (args,)

            # Sort field indices from the slicing
            names = tuple(x for x in args if isinstance(x, str))
            args = tuple(x for x in args if not isinstance(x, str))

            if len(names) != 0:
                raise TypeError("Field name selections are not allowed for write.")

            # Validate the input array
            val = numpy.asarray(val, order='C')

            # Check for array dtype compatibility and convert
            if self.dtype.subdtype is not None:
                shp = self.dtype.subdtype[1]
                if val.shape[-len(shp):] != shp:
                    raise TypeError("Can't broadcast to array dimension %s" % (shp,))
                mtype = h5t.py_create(numpy.dtype((val.dtype, shp)))
                mshape = val.shape[0:len(val.shape)-len(shp)]
            else:
                mshape = val.shape
                mtype = None

            # Perform the dataspace selection
            selection = sel.select(self.shape, args)

            if selection.nselect == 0:
                return

            # Broadcast scalars if necessary
            # TODO: fix scalar broadcasting for array types
            if mshape == () and selection.mshape != () and self.dtype.subdtype is None:
                val2 = numpy.empty(selection.mshape[-1], dtype=val.dtype)
                val2[...] = val
                val = val2
            
            # Perform the write, with broadcasting
            mspace = h5s.create_simple(mshape, (h5s.UNLIMITED,)*len(mshape))
            for fspace in selection.broadcast(mshape):
                self.id.write(mspace, fspace, val, mtype)

    def read_direct(self, dest, source_sel=None, dest_sel=None):
        """ Read data directly from HDF5 into an existing NumPy array.

        The destination array must be C-contiguous and writable.
        Selections may be any operator class (HyperSelection, etc) in
        h5py.selections, or the output of numpy.s_[<args>].

        Broadcasting is supported for simple indexing.
        """

        if source_sel is None:
            source_sel = sel.SimpleSelection(self.shape)
        else:
            source_sel = sel.select(self.shape, source_sel)  # for numpy.s_
        fspace = source_sel._id

        if dest_sel is None:
            dest_sel = sel.SimpleSelection(dest.shape)
        else:
            dest_sel = sel.select(dest.shape, dest_sel)

        for mspace in dest_sel.broadcast(source_sel.mshape):
            self.id.read(mspace, fspace, dest)

    def write_direct(self, source, source_sel=None, dest_sel=None):
        """ Write data directly to HDF5 from a NumPy array.

        The source array must be C-contiguous.  Selections may be any
        operator class (HyperSelection, etc) in h5py.selections, or
        the output of numpy.s_[<args>].

        Broadcasting is supported for simple indexing.
        """

        if source_sel is None:
            source_sel = sel.SimpleSelection(source.shape)
        else:
            source_sel = sel.select(source.shape, source_sel)  # for numpy.s_
        mspace = source_sel._id

        if dest_sel is None:
            dest_sel = sel.SimpleSelection(self.shape)
        else:
            dest_sel = sel.select(self.shape, dest_sel)

        for fspace in dest_sel.broadcast(source_sel.mshape):
            self.id.write(mspace, fspace, source)

    def __repr__(self):
        with self._lock:
            try:
                return '<HDF5 dataset "%s": shape %s, type "%s">' % \
                    (_hbasename(self.name), self.shape, self.dtype.str)
            except Exception:
                return "<Closed HDF5 dataset>"

class AttributeManager(_LockableObject, _DictCompat):

    """ Allows dictionary-style access to an HDF5 object's attributes.

        These are created exclusively by the library and are available as
        a Python attribute at <object>.attrs

        Like the members of groups, attributes provide a minimal dictionary-
        style interface.  Anything which can be reasonably converted to a
        Numpy array or Numpy scalar can be stored.

        Attributes are automatically created on assignment with the
        syntax <obj>.attrs[name] = value, with the HDF5 type automatically
        deduced from the value.  Existing attributes are overwritten.

        To modify an existing attribute while preserving its type, use the
        method modify().  To specify an attribute of a particular type and
        shape (or to create an empty attribute), use create().
    """

    def __init__(self, parent):
        """ Private constructor.
        """
        self.id = parent.id

    def __getitem__(self, name):
        """ Read the value of an attribute.
        """
        with self._lock:
            attr = h5a.open(self.id, name)

            arr = numpy.ndarray(attr.shape, dtype=attr.dtype, order='C')
            attr.read(arr)

            if len(arr.shape) == 0:
                return numpy.asscalar(arr)
            return arr

    def __setitem__(self, name, value):
        """ Set a new attribute, overwriting any existing attribute.

        The type and shape of the attribute are determined from the data.  To
        use a specific type or shape, or to preserve the type of an attribute,
        use the methods create() and modify().

        Broadcasting isn't supported for attributes.
        """
        with self._lock:
            self.create(name, data=value)

    def __delitem__(self, name):
        """ Delete an attribute (which must already exist). """
        h5a.delete(self.id, name)

    def create(self, name, data=None, shape=None, dtype=None):
        """ Create a new attribute, overwriting any existing attribute.

        name:   Name of the new attribute (required)
        data:   An array to initialize the attribute.
                Required unless "shape" is given.
        shape:  Shape of the attribute.  Overrides data.shape if both are
                given.  The total number of points must be unchanged.
        dtype:  Data type of the attribute.  Overrides data.dtype if both
                are given.  Must be conversion-compatible with data.dtype.
        """
        with self._lock:
            if data is not None:
                data = numpy.asarray(data, order='C', dtype=dtype)
                if shape is None:
                    shape = data.shape
                elif numpy.product(shape) != numpy.product(data.shape):
                    raise ValueError("Shape of new attribute conflicts with shape of data")
                    
                if dtype is None:
                    dtype = data.dtype

            if dtype is None:
                dtype = numpy.dtype('f')
            if shape is None:
                raise ValueError('At least one of "shape" or "data" must be given')

            space = h5s.create_simple(shape)
            htype = h5t.py_create(dtype, logical=True)

            if name in self:
                h5a.delete(self.id, name)

            attr = h5a.create(self.id, name, htype, space)
            if data is not None:
                attr.write(data)

    def modify(self, name, value):
        """ Change the value of an attribute while preserving its type.

        Differs from __setitem__ in that the type of an existing attribute
        is preserved.  Useful for interacting with externally generated files.

        If the attribute doesn't exist, it will be automatically created.
        """
        with self._lock:
            if not name in self:
                self[name] = value
            else:
                value = numpy.asarray(value, order='C')

                attr = h5a.open(self.id, name)

                # Allow the case of () <-> (1,)
                if (value.shape != attr.shape) and not \
                   (numpy.product(value.shape)==1 and numpy.product(attr.shape)==1):
                    raise TypeError("Shape of data is incompatible with existing attribute")
                attr.write(value)

    def __len__(self):
        """ Number of attributes attached to the object. """
        # I expect we will not have more than 2**32 attributes
        return h5a.get_num_attrs(self.id)

    def __iter__(self):
        """ Iterate over the names of attributes. """
        with self._lock:
            attrlist = []
            def iter_cb(name, *args):
                attrlist.append(name)
            h5a.iterate(self.id, iter_cb)

            for name in attrlist:
                yield name

    def __contains__(self, name):
        """ Determine if an attribute exists, by name. """
        return h5a.exists(self.id, name)

    def __repr__(self):
        with self._lock:
            try:
                return '<Attributes of HDF5 object "%s" (%d)>' % \
                    (_hbasename(h5i.get_name(self.id)), len(self))
            except Exception:
                return "<Attributes of closed HDF5 object>"


class Datatype(HLObject):

    """
        Represents an HDF5 named datatype stored in a file.

        To store a datatype, simply assign it to a name in a group:

        >>> MyGroup["name"] = numpy.dtype("f")
        >>> named_type = MyGroup["name"]
        >>> assert named_type.dtype == numpy.dtype("f")
    """

    @property
    def dtype(self):
        """Numpy dtype equivalent for this datatype"""
        return self.id.dtype

    def __init__(self, grp, name):
        """ Private constructor.
        """
        with grp._lock:
            HLObject.__init__(self, grp)
            self.id = h5t.open(grp.id, name)
            self._attrs = AttributeManager(self)

    def __repr__(self):
        with self._lock:
            try:
                return '<HDF5 named type "%s" (dtype %s)>' % \
                    (_hbasename(self.name), self.dtype.str)
            except Exception:
                return "<Closed HDF5 named type>"


# Re-export functions for new type infrastructure

def new_vlen(basetype):
    """ Create a NumPy dtype representing a variable-length type.

    Currently only the native string type (str) is allowed.

    The kind of the returned dtype is always "O"; metadata attached to the
    dtype allows h5py to perform translation between HDF5 VL types and
    native Python objects.
    """
    return h5t.py_new_vlen(basetype)

def get_vlen(dtype):
    """ Return the "base" type from a NumPy dtype which represents a 
    variable-length type, or None if the type is not of variable length.

    Currently only variable-length strings, created with new_vlen(), are
    supported.
    """
    return h5t.py_get_vlen(dtype)

def new_enum(dtype, values):
    """ Create a new enumerated type, from an integer base type and dictionary
    of values.

    The values dict should contain string keys and int/long values.
    """
    return h5t.py_new_enum(numpy.dtype(dtype), values)

def get_enum(dtype):
    """ Extract the values dictionary from an enumerated type, returning None
    if the given dtype does not represent an enum.
    """
    return h5t.py_get_enum(dtype)




