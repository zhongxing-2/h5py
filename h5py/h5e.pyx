
"""
    Implements HDF5 error support and Python exception translation.
"""


include "config.pxi"

from python_exc cimport PyErr_SetString
from h5 cimport SmartStruct

import _stub


# === Exception hierarchy based on major error codes ==========================

class H5Error(Exception):
    """ Base class for internal HDF5 library exceptions.
    """
    pass

#    H5E_ARGS,                   # invalid arguments to routine
class ArgsError(H5Error):
    """ H5E_ARGS """
    pass
        
#    H5E_RESOURCE,               # resource unavailable   
class ResourceError(H5Error):
    """ H5E_RESOURCE """
    pass
                    
#   H5E_INTERNAL,               #  Internal error (too specific to document)
class InternalError(H5Error):
    """ H5E_INTERNAL """
    pass

#    H5E_FILE,                   # file Accessability       
class FileError(H5Error):
    """ H5E_FILE """
    pass
                  
#    H5E_IO,                     # Low-level I/O                      
class LowLevelIOError(H5Error):
    """ H5E_IO """
    pass
        
#    H5E_FUNC,                   # function Entry/Exit     
class FuncError(H5Error):
    """ H5E_FUNC """
    pass
                   
#    H5E_ATOM,                   # object Atom         
class AtomError(H5Error):
    """ H5E_ATOM """
    pass
                       
#   H5E_CACHE,                  # object Cache        
class CacheError(H5Error):
    """ H5E_CACHE """
    pass
                       
#   H5E_BTREE,                  # B-Tree Node           
class BtreeError(H5Error):
    """ H5E_BTREE """
    pass
                     
#    H5E_SYM,                    # symbol Table         
class SymbolError(H5Error):
    """ H5E_SYM """
    pass
                      
#   H5E_HEAP,                   # Heap  
class HeapError(H5Error):
    """ H5E_HEAP """
    pass
                                     
#    H5E_OHDR,                   # object Header     
class ObjectHeaderError(H5Error):
    """ H5E_OHDR """
    pass
                         
#    H5E_DATATYPE,               # Datatype    
class DatatypeError(H5Error):
    """ H5E_DATATYPE """
    pass
                               
#    H5E_DATASPACE,              # Dataspace                      
class DataspaceError(H5Error):
    """ H5E_DATASPACE """
    pass
            
#    H5E_DATASET,                # Dataset                        
class DatasetError(H5Error):
    """ H5E_DATASET """
    pass
            
#    H5E_STORAGE,                # data storage                
class StorageError(H5Error):
    """ H5E_STORAGE """
    pass
               
#    H5E_PLIST,                  # Property lists                  
class PropertyError(H5Error):
    """ H5E_PLIST """
    pass
           
#    H5E_ATTR,                   # Attribute     
class AttrError(H5Error):
    """ H5E_ATTR """
    pass
                             
#    H5E_PLINE,                  # Data filters       
class FilterError(H5Error):
    """ H5E_PLINE """
    pass
                        
#    H5E_EFL,                    # External file list                         
class FileListError(H5Error):
    """ H5E_EFL """
    pass

#    H5E_REFERENCE,              # References          
class RefError(H5Error):
    """ H5E_REFERENCE """
    pass
                       
#    H5E_VFL,                    # Virtual File Layer        
class VirtualFileError(H5Error):
    """ H5E_VFL """
    pass

#    H5E_TST,                    # Ternary Search Trees                       
class TSTError(H5Error):
    """ H5E_TST """
    pass

#    H5E_RS,                     # Reference Counted Strings        
class RSError(H5Error):
    """ H5E_RS """
    pass
          
#    H5E_ERROR,                  # Error API                    
class ErrorError(H5Error):
    """ H5E_ERROR """
    pass
              
#    H5E_SLIST                   # Skip Lists        
class SkipListError(H5Error):
    """ H5E_SLIST """
    pass  

# Traditional major error classes.  One of these (or H5Error) is always a
# parent class of the raised exception.
cdef dict _major_table = {
    H5E_ARGS: ArgsError,
    H5E_RESOURCE: ResourceError,
    H5E_INTERNAL: InternalError,
    H5E_FILE: FileError,
    H5E_IO: LowLevelIOError,
    H5E_FUNC: FuncError,
    H5E_ATOM: AtomError,
    H5E_CACHE: CacheError,
    H5E_BTREE: BtreeError,
    H5E_SYM: SymbolError,
    H5E_HEAP: HeapError,
    H5E_OHDR: ObjectHeaderError,
    H5E_DATATYPE: DatatypeError,
    H5E_DATASPACE: DataspaceError,
    H5E_DATASET: DatasetError,
    H5E_STORAGE: StorageError,
    H5E_PLIST: PropertyError,
    H5E_ATTR: AttrError,
    H5E_PLINE: FilterError,
    H5E_EFL: FileListError,
    H5E_REFERENCE: RefError,
    H5E_VFL: VirtualFileError,
    H5E_TST: TSTError,
    H5E_RS: RSError,
    H5E_ERROR: ErrorError,
    H5E_SLIST: SkipListError}

# Python-style minor error classes.  If the minor error code matches an entry
# in this dict, the generated exception will also descend from the indicated
# built-in exception.
cdef dict _minor_table = {
    H5E_SEEKERROR:      IOError,    # Seek failed 
    H5E_READERROR:      IOError,    # Read failed  
    H5E_WRITEERROR:     IOError,    # Write failed  
    H5E_CLOSEERROR:     IOError,    # Close failed 
    H5E_OVERFLOW:       IOError,    # Address overflowed 
    H5E_FCNTL:          IOError,    # File control (fcntl) failed

    H5E_NOFILTER:       IOError,    # Requested filter is not available 
    H5E_CALLBACK:       IOError,    # Callback failed 
    H5E_CANAPPLY:       IOError,    # Error from filter 'can apply' callback 
    H5E_SETLOCAL:       IOError,    # Error from filter 'set local' callback 
    H5E_NOENCODER:      IOError,    # Filter present but encoding disabled 

    H5E_FILEEXISTS:     ValueError,  # File already exists 
    H5E_FILEOPEN:       ValueError,  # File already open 
    H5E_NOTHDF5:        ValueError,  # Not an HDF5 file 
    H5E_BADFILE:        ValueError,  # Bad file ID accessed

    H5E_BADATOM:        ValueError,  # Unable to find atom information (already closed?) 
    H5E_BADGROUP:       ValueError,  # Unable to find ID group information 
    H5E_BADSELECT:      ValueError,  # Invalid selection (hyperslabs)
    H5E_UNINITIALIZED:  ValueError,  # Information is uinitialized 
    H5E_UNSUPPORTED:    NotImplementedError,    # Feature is unsupported 

    H5E_NOTFOUND:       KeyError,    # Object not found 
    H5E_CANTINSERT:     ValueError,   # Unable to insert object 

    H5E_BADTYPE:        TypeError,   # Inappropriate type 
    H5E_BADRANGE:       ValueError,  # Out of range 
    H5E_BADVALUE:       ValueError,  # Bad value

    H5E_EXISTS:         ValueError,  # Object already exists 
    H5E_CANTCONVERT:    TypeError    # Can't convert datatypes 
  }

# "Fudge" table to accomodate annoying inconsistencies in HDF5's use 
# of the minor error codes.  If a (major, minor) entry appears here,
# it will override any entry in the minor error table.
cdef dict _exact_table = {
    (H5E_CACHE, H5E_BADVALUE):      IOError,  # obj create w/o write intent 1.8
    (H5E_RESOURCE, H5E_CANTINIT):   IOError,  # obj create w/o write intent 1.6
    (H5E_INTERNAL, H5E_SYSERRSTR):  IOError,  # e.g. wrong file permissions
  }


# === Error stack inspection ==================================================

cdef class ErrorStackElement(SmartStruct):

    """
        Encapsulation of the H5E_error_t structure.
    """
    
    cdef H5E_error_t e

    property func_name:
        """ Name of HDF5 C function in which error occurred """
        def __get__(self):
            return self.e.func_name
    property desc:
        """ Brief description of the error """
        def __get__(self):
            s = self.e.desc
            return s.capitalize()
    property code:
        """ A 2-tuple of error codes (major, minor) """
        def __get__(self):
            return (<int>self.e.maj_num, <int>self.e.min_num)
    property code_desc:
        """ A 2-tuple of strings (major description, minor description) """
        def __get__(self):
            return H5Eget_major(self.e.maj_num), H5Eget_minor(self.e.min_num)

def get_major(int code):
    """ Get description for a major error code """
    return H5Eget_major(<H5E_major_t>code)

def get_minor(int code):
    """ Get description for a minor error code """
    return H5Eget_minor(<H5E_minor_t>code)

_verbose = False
def verbose(bint v):
    """ (BOOL verbose)

    If FALSE (default), exception messages are a single line.  If TRUE,
    an HDF5 stack trace is attached.
    """

    global _verbose
    _verbose = bool(v)

class ErrorStack(list):

    """
        Represents the HDF5 error stack
    """

    def __init__(self, *args, **kwds):
        list.__init__(self, *args, **kwds)
        H5Ewalk(H5E_WALK_UPWARD, walk_cb, <void*>self)

    def get_exc_msg(self):
        """ Returns a 2-tuple (exception class, string message) representing
            the current error condition, or None if no error exists.
        """
        global _verbose

        if len(self) == 0:
            return None

        major, minor = self[0].code

        maj_class = _major_table.get(major, H5Error)
        min_class = _exact_table.get((major, minor), None)
        if min_class is None:
            min_class = _minor_table.get(minor, None)

        if min_class is None:
            exc = maj_class
        else:
            exc = _stub.generate_class(maj_class, min_class)

        msg = "%s (%s: %s)" % (self[0].desc, self[0].code_desc[0],
                                                   self[0].code_desc[1])
        if _verbose:
            msg += '\n'+str(self)

        return exc, msg
 
    def __str__(self):
        """ Return a string representation of the error stack """
        if len(self) == 0:
            return "No HDF5 error recorded"
        s = 'HDF5 Error Stack:'
        for idx, el in enumerate(self):
            s += '\n    %d: "%s" at %s' % (idx, el.desc, el.func_name)
            s += '\n        %s :: %s' % el.code_desc

        return s

cdef herr_t walk_cb(int n, H5E_error_t *err_desc, void* stack_in):
    # Callback function to extract elements from the HDF5 error stack

    stack = <object>stack_in

    cdef ErrorStackElement element
    element = ErrorStackElement()

    element.e = err_desc[0]
    stack += [element]

    return 0

cdef herr_t err_callback(void* client_data) with gil:
    # Callback which sets Python exception based on the current error stack.

    # MUST be "with gil" as it can be called by nogil HDF5 routines.
    # By definition any function for which this can be called already
    # holds the PHIL.
    
    stack = ErrorStack()

    a = stack.get_exc_msg()
    if a is None:
        exc, msg = RuntimeError, "No HDF5 exception information found"
    else:
        exc, msg = a

    PyErr_SetString(exc, msg)  # Can't use "raise" or the traceback points here

    return 1

cpdef int register_thread() except -1:
    """ ()

    Register the current thread for native HDF5 exception support.  This is
    automatically called by h5py on startup.  Safe to call more than once.        
    """
    if H5Eset_auto(err_callback, NULL) < 0:
        raise RuntimeError("Failed to register HDF5 exception callback")
    return 0


