
"""
    Utility functions for high-level modules.
"""
from __future__ import with_statement
from h5py import h5s, h5z, h5p, h5d
import numpy as np

CHUNK_BASE = 16*1024    # Multiplier by which chunks are adjusted
CHUNK_MIN = 8*1024      # Soft lower limit (8k)
CHUNK_MAX = 1024*1024   # Hard upper limit (1M)

_COMP_FILTERS = {'gzip': h5z.FILTER_DEFLATE,
                'szip': h5z.FILTER_SZIP,
                'lzf': h5z.FILTER_LZF }

DEFAULT_GZIP = 4
DEFAULT_SZIP = ('nn', 8)

def _gen_filter_tuples():
    decode = []
    encode = []
    for name, code in _COMP_FILTERS.iteritems():
        if h5z.filter_avail(code):
            info = h5z.get_filter_info(code)
            if info & h5z.FILTER_CONFIG_ENCODE_ENABLED:
                encode.append(name)
            if info & h5z.FILTER_CONFIG_DECODE_ENABLED:
                decode.append(name)

    return tuple(decode), tuple(encode)

decode, encode = _gen_filter_tuples()

def generate_dcpl(shape, dtype, chunks, compression, compression_opts,
                  shuffle, fletcher32, maxshape):
    """ Generate a dataset creation property list.

        Checks range and correctness of each argument.  Does not check
        for disallowed arguments.

        chunks:         None or tuple with len == len(shape)
        compression:    None or in 'gzip', 'lzf', 'szip'
        compression_opts: None or <arbitrary>
        shuffle:        T/F
        fletcher32:     T/F
        maxshape:       None or tuple with len == len(shape)
    """

    # Validate and normalize arguments

    if shape == ():
        if maxshape and maxshape != ():
            raise TypeError("Scalar datasets cannot be extended")
        return h5p.create(h5p.DATASET_CREATE)

    fletcher32 = bool(fletcher32)

    def rq_tuple(tpl, name):
        if tpl not in (None, True):
            try:
                tpl = tuple(tpl)
                if len(tpl) != len(shape):
                    raise ValueError('"%s" must have same rank as dataset shape' % name)
            except TypeError:
                raise TypeError('"%s" argument must be None or a sequence object' % name) 
 
    rq_tuple(chunks, 'chunks')
    rq_tuple(maxshape, 'maxshape')

    if compression is not None:

        if shuffle is None:
            shuffle = True

        if compression not in _COMP_FILTERS:
            raise ValueError("Compression method must be one of %s" % ", ".join(_COMP_FILTERS))
        if compression == 'gzip':
            if compression_opts is None:
                gzip_level = DEFAULT_GZIP
            elif compression_opts in range(10):
                gzip_level = compression_opts
            else:
                raise ValueError("GZIP setting must be an integer from 0-9, not %r" % compression_opts)
        elif compression == 'lzf':
            if compression_opts is not None:
                raise ValueError("LZF compression filter accepts no options")
        elif compression == 'szip':
            if compression_opts is None:
                compression_opts = DEFAULT_SZIP

            err = "SZIP options must be a 2-tuple ('ec'|'nn', even integer 0-32)"
            try:
                szmethod, szpix = compression_opts
            except TypeError:
                raise TypeError(err)
            if szmethod not in ('ec', 'nn'):
                raise ValueError(err)
            if not (0<szpix<32 and szpix%2 == 0):
                raise ValueError(err)

    # End argument validation

    if (chunks is True) or \
    (chunks is None and any((shuffle, fletcher32, compression, maxshape))):
        chunks = guess_chunk(shape, dtype.itemsize)
        
    if maxshape is True:
        maxshape = (None,)*len(shape)

    plist = h5p.create(h5p.DATASET_CREATE)
    if chunks is not None:
        plist.set_chunk(chunks)
        plist.set_fill_time(h5d.FILL_TIME_ALLOC)

    # MUST be first, to prevent 1.6/1.8 compatibility glitch
    if fletcher32:
        plist.set_fletcher32()

    if shuffle:
        plist.set_shuffle()

    if compression == 'gzip':
        plist.set_deflate(gzip_level)
    elif compression == 'lzf':
        plist.set_filter(h5z.FILTER_LZF, h5z.FLAG_OPTIONAL)
    elif compression == 'szip':
        opts = {'ec': h5z.SZIP_EC_OPTION_MASK, 'nn': h5z.SZIP_NN_OPTION_MASK}
        plist.set_szip(opts[szmethod], szpix)

    return plist

def get_filters(plist):
    """ Extract a dictionary of active filters from a DCPL, along with
    their settings
    """

    filters = {h5z.FILTER_DEFLATE: 'gzip', h5z.FILTER_SZIP: 'szip',
               h5z.FILTER_SHUFFLE: 'shuffle', h5z.FILTER_FLETCHER32: 'fletcher32',
               h5z.FILTER_LZF: 'lzf'}
    szopts = {h5z.SZIP_EC_OPTION_MASK: 'ec', h5z.SZIP_NN_OPTION_MASK: 'nn'}

    pipeline = {}

    nfilters = plist.get_nfilters()

    for i in range(nfilters):

        code, flags, vals, desc = plist.get_filter(i)

        if code == h5z.FILTER_DEFLATE:
            vals = vals[0] # gzip level

        elif code == h5z.FILTER_SZIP:
            mask, pixels = vals[0:2]
            if mask & h5z.SZIP_EC_OPTION_MASK:
                mask = 'ec'
            elif mask & h5z.SZIP_NN_OPTION_MASK:
                mask = 'nn'
            else:
                raise TypeError("Unknown SZIP configuration")
            vals = (mask, pixels)
        else:
            if len(vals) == 0:
                vals = None

        pipeline[filters.get(code, str(code))] = vals

    return pipeline

def guess_chunk(shape, typesize):
    """ Guess an appropriate chunk layout for a dataset, given its shape and
        the size of each element in bytes.  Will allocate chunks only as large
        as MAX_SIZE.  Chunks are generally close to some power-of-2 fraction of
        each axis, slightly favoring bigger values for the last index.
    """

    ndims = len(shape)
    if ndims == 0:
        raise ValueError("Chunks not allowed for scalar datasets.")

    chunks = np.array(shape, dtype='=f8')

    # Determine the optimal chunk size in bytes using a PyTables expression.
    # This is kept as a float.
    dset_size = np.product(chunks)*typesize
    target_size = CHUNK_BASE * (2**np.log10(dset_size/(1024.*1024)))

    if target_size > CHUNK_MAX:
        target_size = CHUNK_MAX
    elif target_size < CHUNK_MIN:
        target_size = CHUNK_MIN

    idx = 0
    while True:
        # Repeatedly loop over the axes, dividing them by 2.  Stop when:
        # 1a. We're smaller than the target chunk size, OR
        # 1b. We're within 50% of the target chunk size, AND
        #  2. The chunk is smaller than the maximum chunk size

        chunk_bytes = np.product(chunks)*typesize

        if (chunk_bytes < target_size or \
         abs(chunk_bytes-target_size)/target_size < 0.5) and \
         chunk_bytes < CHUNK_MAX:
            break

        chunks[idx%ndims] = np.ceil(chunks[idx%ndims] / 2.0)
        idx += 1

    return tuple(long(x) for x in chunks)








