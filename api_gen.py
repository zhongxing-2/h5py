import re
import warnings
import os.path as op

class BadLineError(Exception):
    pass

class Line(object):

    """
        Represents one line from the api_functions.txt file.
        
        Exists to provide the following attributes:
        
        mpi:        Bool indicating if MPI required
        error:      Bool indicating if special error handling required
        version:    None or a minimum-version tuple
        code:       String with function return type
        fname:      String with function name
        sig:        String with raw function signature
        args:       String with sequence of arguments to call function
        
        Example:    MPI ERROR 1.8.12 int foo(char* a, size_t b)
        
        .mpi:       True
        .error:     True
        .version:   (1, 8, 12)
        .code:      "int"
        .fname:     "foo"
        .sig:       "char* a, size_t b"
        .args:      "a, b"
    """
        
    PATTERN = re.compile("""(?P<mpi>(MPI)[ ]+)?
                            (?P<error>(ERROR)[ ]+)?
                            (?P<version>([0-9]\.[0-9]\.[0-9]))?
                            ([ ]+)?
                            (?P<code>(unsigned[ ]+)?[a-zA-Z_]+[a-zA-Z0-9_]*\**)[ ]+
                            (?P<fname>[a-zA-Z_]+[a-zA-Z0-9_]*)[ ]*
                            \((?P<sig>[a-zA-Z0-9_,* ]*)\)
                            """, re.VERBOSE)

    SIG_PATTERN = re.compile("""
                            (unsigned[ ]+)?
                            (?:[a-zA-Z_]+[a-zA-Z0-9_]*\**)
                            [ ]+[ *]*
                            (?P<param>[a-zA-Z_]+[a-zA-Z0-9_]*)
                            """, re.VERBOSE)
                            
    def __init__(self, text):
        """ Break the line into pieces and populate object attributes.
        
        text: A valid function line, with leading/trailing whitespace stripped.
        """
        
        m = self.PATTERN.match(text)
        if m is None:
            raise ValueError("Invalid line encountered: {}".format(text))
            
        parts = m.groupdict()
        
        self.mpi = parts['mpi'] is not None
        self.error = parts['error'] is not None
        self.version = parts['version']
        if self.version is not None:
            self.version = tuple(int(x) for x in self.version.split('.'))
        self.code = parts['code']
        self.fname = parts['fname']
        self.sig = parts['sig']

        self.args = self.SIG_PATTERN.findall(self.sig)
        if self.args is None:
            raise ValueError("Invalid function signature: {}".format(self.sig))
        self.args = ", ".join(x[1] for x in self.args)


raw_preamble = """\
include "config.pxi"
from api_types_hdf5 cimport *
from api_types_ext cimport *

"""

def_preamble = """\
include "config.pxi"

from api_types_hdf5 cimport *
from api_types_ext cimport *

"""

imp_preamble = """\
include "config.pxi"
from api_types_ext cimport *
from api_types_hdf5 cimport *

cimport _hdf5

from _errors cimport set_exception
"""

class FunctionCruncher2(object):

    def run(self):

        # Function definitions file
        self.functions = open(op.join('h5py', 'api_functions.txt'), 'r')

        # Create output files
        self.raw_defs =     open(op.join('h5py', '_hdf5.pxd'), 'w')
        self.cython_defs =  open(op.join('h5py', 'defs.pxd'), 'w')
        self.cython_imp =   open(op.join('h5py', 'defs.pyx'), 'w')

        self.raw_defs.write(raw_preamble)
        self.cython_defs.write(def_preamble)
        self.cython_imp.write(imp_preamble)

        for text in self.functions:
        
            # Directive specifying a header file
            if not text.startswith(' ') and not text.startswith('#') and \
            len(text.strip()) > 0:
                inc = text.split(':')[0]
                self.raw_defs.write('cdef extern from "%s.h":\n' % inc)
                continue
            
            # Whitespace or comment line
            text = text.strip()
            if len(text) == 0 or text[0] == '#':
                continue

            # Valid function line
            self.line = Line(text)
            self.write_raw_sig()
            self.write_cython_sig()
            self.write_cython_imp()
    
        self.functions.close()
        self.cython_imp.close()
        self.cython_defs.close()
        self.raw_defs.close()

    def add_cython_if(self, block):
        """ Wrap a block of code in the required "IF" checks """
        
        def wrapif(condition, code):
            code = code.replace('\n', '\n    ', code.count('\n')-1) # Yes, -1.
            code = "IF {}:\n    {}".format(condition, code)
            return code

        if self.line.mpi:
            block = wrapif('MPI', block)
        if self.line.version is not None:
            block = wrapif('HDF5_VERSION >= {0.version}'.format(self.line), block)

        return block

    def write_raw_sig(self):
        """ Add "cdef extern"-style definition for an HDF5 function """

        raw_sig = "  {0.code} {0.fname}({0.sig}) except *\n".format(self.line)
        raw_sig = self.add_cython_if(raw_sig)
        self.raw_defs.write(raw_sig)

    def write_cython_sig(self):
        """ Add Cython signature for wrapper function """

        cython_sig = "cdef {0.code} {0.fname}({0.sig}) except *\n".format(self.line)
        cython_sig = self.add_cython_if(cython_sig)
        self.cython_defs.write(cython_sig)

    def write_cython_imp(self):
        """ Build a Cython wrapper implementation """

        # Figure out what test and return value to use with error reporting
        if '*' in self.line.code or self.line.code in ('H5T_conv_t',):
            condition = "==NULL"
            retval = "NULL"
        elif self.line.code in ('int', 'herr_t', 'htri_t', 'hid_t','hssize_t','ssize_t') \
          or re.match(r'H5[A-Z]+_[a-zA-Z_]+_t', self.line.code):
            condition = "<0"
            retval = "-1"
        elif self.line.code in ('unsigned int','haddr_t','hsize_t','size_t'):
            condition = "==0"
            retval = 0
        else:
            raise ValueError("Return code <<%s>> unknown" % self.line.code)

        # Have to use except * because Cython can't handle special types here
        imp = """\
cdef {0.code} {0.fname}({0.sig}) except *:
    cdef {0.code} r
    r = _hdf5.{0.fname}({0.args})
    if r{condition}:
        if set_exception():
            return <{0.code}>{retval}
        elif {0.error}:
            raise RuntimeError("Unspecified error in {0.fname} (return value {condition})")
    return r

"""
        imp = imp.format(self.line, condition=condition, retval=retval)
        imp = self.add_cython_if(imp)
        self.cython_imp.write(imp)

def run():
    fc = FunctionCruncher2()
    fc.run()

if __name__ == '__main__':
    run()
