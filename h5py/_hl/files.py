import weakref
import sys
import os

from .base import HLObject
from .group import Group
from h5py import h5f, h5p, h5i, h5fd, h5t

libver_dict = {'earliest': h5f.LIBVER_EARLIEST, 'latest': h5f.LIBVER_LATEST}
libver_dict_r = dict((y,x) for x, y in libver_dict.iteritems())

def make_fapl(driver,libver,**kwds):
    """ Set up a file access property list """
    plist = h5p.create(h5p.FILE_ACCESS)
    plist.set_fclose_degree(h5f.CLOSE_STRONG)

    if libver is not None:
        if libver in libver_dict:
            low = libver_dict[libver]
            high = h5f.LIBVER_LATEST
        else:
            low, high = (libver_dict[x] for x in libver)
        plist.set_libver_bounds(low, high)

    if driver is None or (driver=='windows' and sys.platform=='win32'):
        return plist

    if(driver=='sec2'):
        plist.set_fapl_sec2(**kwds)
    elif(driver=='stdio'):
        plist.set_fapl_stdio(**kwds)
    elif(driver=='core'):
        plist.set_fapl_core(**kwds)
    elif(driver=='family'):
        plist.set_fapl_family(memb_fapl=plist.copy(), **kwds)
    else:
        raise ValueError('Unknown driver type "%s"' % driver)

    return plist

def make_fid(name, mode, plist):
    """ Get a new FileID by opening or creating a file.
    Also validates mode argument."""
    if mode == 'r':
        fid = h5f.open(name, h5f.ACC_RDONLY, fapl=plist)
    elif mode == 'r+':
        fid = h5f.open(name, h5f.ACC_RDWR, fapl=plist)
    elif mode == 'w-':
        fid = h5f.create(name, h5f.ACC_EXCL, fapl=plist)
    elif mode == 'w':
        fid = h5f.create(name, h5f.ACC_TRUNC, fapl=plist)
    elif mode == 'a' or mode is None:
        try:
            fid = h5f.open(name, h5f.ACC_RDWR, fapl=plist)
        except IOError:
            fid = h5f.create(name, h5f.ACC_EXCL, fapl=plist)
    else:
        raise ValueError("Invalid mode; must be one of r, r+, w, w-, a")
    return fid

def make_lapl():
    """Default link access property list"""

    lapl = h5p.create(h5p.LINK_ACCESS)
    fapl = h5p.create(h5p.FILE_ACCESS)
    fapl.set_fclose_degree(h5f.CLOSE_STRONG)
    lapl.set_elink_fapl(fapl)
    return lapl

def make_lcpl():
    """Default link creation property list"""
    lcpl = h5p.create(h5p.LINK_CREATE)
    lcpl.set_create_intermediate_group(True)
    return lcpl

class File(Group):

    """
        Represents an HDF5 file.
    """

    @property
    def filename(self):
        """File name on disk"""
        name = h5f.get_name(self.fid)
        try:
            return name.decode(sys.getfilesystemencoding())
        except (UnicodeError, LookupError):
            return name

    @property
    def driver(self):
        """Low-level HDF5 file driver used to open file"""
        drivers = {h5fd.SEC2: 'sec2', h5fd.STDIO: 'stdio',
                   h5fd.CORE: 'core', h5fd.FAMILY: 'family',
                   h5fd.WINDOWS: 'windows'}
        return drivers.get(self.fid.get_access_plist().get_driver(), 'unknown')

    @property
    def mode(self):
        """ Python mode used to open file """
        if not hasattr(self._shared, 'mode'):
            self._shared.mode = {h5f.ACC_RDONLY: 'r', h5f.ACC_RDWR: 'r+'}.get(self.fid.get_intent())
        return self._shared.mode

    @property
    def fid(self):
        """File ID (backwards compatibility) """
        return self.id

    @property
    def libver(self):
        """File format version bounds (2-tuple: low, high)"""
        bounds = self.id.get_access_plist().get_libver_bounds()
        return tuple(libver_dict_r[x] for x in bounds)

    def __init__(self, name, mode=None, driver=None, libver=None, **kwds):
        """Create a new file object.

        See the h5py user guide for a detailed explanation of the options.

        name
            Name of the file on disk.  Note: for files created with the 'core'
            driver, HDF5 still requires this be non-empty.
        driver
            Name of the driver to use.  Legal values are None (default,
            recommended), 'core', 'sec2' (UNIX), 'stdio'.
        libver
            Library version bounds.  Currently only the strings 'earliest'
            and 'latest' are defined.
        Additional keywords
            Passed on to the selected file driver.
        """
        if isinstance(name, HLObject):
            fid = h5i.get_file_id(name.id)
        else:
            try:
                # If the byte string doesn't match the default encoding, just
                # pass it on as-is.  Note Unicode objects can always be encoded.
                name = name.encode(sys.getfilesystemencoding())
            except (UnicodeError, LookupError):
                pass
            fapl = make_fapl(driver,libver,**kwds)
            fid = make_fid(name, mode, fapl)
        Group.__init__(self, fid)
        self._shared.lcpl = make_lcpl()
        self._shared.lapl = make_lapl()
        self._shared.mode = mode

    def close(self):
        """ Close the file.  All open objects become invalid """
        # TODO: find a way to square this with having issue 140
        # Not clearing shared state introduces a tiny memory leak, but
        # it goes like the number of files opened in a session.
        #del self._shared
        self.id.close()

    def flush(self):
        """ Tell the HDF5 library to flush its buffers.
        """
        h5f.flush(self.fid)

    def __enter__(self):
        return self

    def __exit__(self,*args):
        if self.id:
            self.close()

    def __repr__(self):
        if not self.id:
            return "<Closed HDF5 file>"
        return '<HDF5 file "%s" (mode %s)>' % \
            (os.path.basename(self.filename), self.mode)



