import re
import warnings


class BadLineError(Exception):
    pass

class UnknownCodeError(Exception):
    pass


# The following files are used to talk to the HDF5 api:
#
# (1) hdf5.pxd:         HDF5 function signatures    (autogenerated)
# (2) hdf5_types.pxd:   HDF5 type definitions       (static)
# (3) defs.pxd:         HDF5 function proxy defs    (autogenerated)
# (4) defs.pyx:         HDF5 function proxies       (autogenerated)

function_pattern = r'([ ]+)?(?P<code>(unsigned[ ]+)?[a-zA-Z_]+[a-zA-Z0-9_]*\**)[ ]+(?P<fname>[a-zA-Z_]+[a-zA-Z0-9_]*)[ ]*\((?P<sig>[a-zA-Z0-9_,* ]*)\)'
sig_pattern = r'(unsigned[ ]+)?(?:[a-zA-Z_]+[a-zA-Z0-9_]*\**)[ ]+[ *]*(?P<param>[a-zA-Z_]+[a-zA-Z0-9_]*)'

fp = re.compile(function_pattern)
sp = re.compile(sig_pattern)

raw_preamble = """\
from api_types_hdf5 cimport *
from api_types_ext cimport *

"""

def_preamble = """\
from api_types_hdf5 cimport *
from api_types_ext cimport *

"""

imp_preamble = """\
from api_types_ext cimport *
from api_types_hdf5 cimport *

cimport _hdf5

from _errors cimport set_exception

"""

class FunctionCruncher2(object):

    def __init__(self, stub=False):
        self.stub = stub

    def run(self):

        # Function definitions file
        self.functions = open('api_functions.txt','r')

        # Create output files
        self.raw_defs =     open('_hdf5.pxd','w')
        self.cython_def =   open('defs.pxd','w')
        self.cython_imp =   open('defs.pyx','w')

        self.raw_defs.write(raw_preamble)
        self.cython_def.write(def_preamble)
        self.cython_imp.write(imp_preamble)

        for line in self.functions:
            if not line or line[0] == '#' or line[0] == '\n':
                continue
            try:
                self.handle_line(line)
            except BadLineError:
                warnings.warn("Skipped <<%s>>" % line)

        self.functions.close()
        self.cython_imp.close()
        self.cython_def.close()
        self.raw_defs.close()

    def handle_line(self, line):
        """ Parse a function definition line and output the correct code
        to each of the output files. """

        if line.startswith(' '):
            line = line.strip()
            if line.startswith('#'):
                return
            m = fp.match(line)
            if m is None:
                raise BadLineError(
                    "Signature for line <<%s>> did not match regexp" % line
                    )
            function_parts = m.groupdict()

            self.raw_defs.write('  '+self.make_raw_sig(function_parts))
            self.cython_def.write(self.make_cython_sig(function_parts))
            self.cython_imp.write(self.make_cython_imp(function_parts))
        else:
            inc = line.split(':')[0]
            self.raw_defs.write('cdef extern from "%s.h":\n' % inc)

    def make_raw_sig(self, function_parts):
        """ Build a "cdef extern"-style definition for an HDF5 function """

        return "%(code)s %(fname)s(%(sig)s)\n" % function_parts

    def make_cython_sig(self, function_parts):
        """ Build Cython signature for wrapper function """

        return "cdef %(code)s %(fname)s(%(sig)s) except *\n" % function_parts

    def make_cython_imp(self, function_parts, stub=False):
        """ Build a Cython wrapper implementation. If stub is True, do
        nothing but call the function and return its value """

        args = sp.findall(function_parts['sig'])
        if args is None:
            raise BadLineError("Can't understand function signature <<%s>>" % function_parts['sig'])
        args = ", ".join(x[1] for x in args)

        # Figure out what conditional to use for the error testing
        code = function_parts['code']
        if '*' in code or code in ('H5T_conv_t',):
            condition = "==NULL"
            retval = "NULL"
        elif code in ('int', 'herr_t', 'htri_t', 'hid_t','hssize_t','ssize_t') \
          or re.match(r'H5[A-Z]+_[a-zA-Z_]+_t',code):
            condition = "<0"
            retval = "-1"
        elif code in ('unsigned int','haddr_t','hsize_t','size_t'):
            condition = "==0"
            retval = 0
        else:
            raise UnknownCodeError("Return code <<%s>> unknown" % self.code)

        parts = function_parts.copy()
        parts.update({'condition': condition, 'retval': retval, 'args': args})

        # Have to use except * because Cython can't handle special types here
        imp = """\
cdef %(code)s %(fname)s(%(sig)s) except *:
    cdef %(code)s r
    r = _hdf5.%(fname)s(%(args)s)
    if r%(condition)s:
        if set_exception():
            return <%(code)s>%(retval)s;
    return r

"""

        stub_imp = """\
cdef %(code)s %(fname)s(%(sig)s) except *:
    return hdf5.%(fname)s(%(args)s)

"""
        return (stub_imp if self.stub else imp) % parts


if __name__ == '__main__':

    import sys
    stub = True if 'stub' in sys.argv else False
    fc = FunctionCruncher2(stub)
    fc.run()



