#######################################################################
#                                                                     #
#                  Python Progs :  dump.py                            #
#                  Aruthor      :  Colby Haggerty                     #
#                  Date         :  2016.01.23                         #
#                                                                     #
#                                                                     #
#######################################################################
import os
import sys 
import pdb
import time
import glob
import struct
import numpy as np
from ._methods import load_param
from ._methods import _num_to_ext

# Change foo.has_key(bar) to bar in foo 
class Dump(object):
    """ class that reads and stores dump file data
        
        TODO: submit my complaint through github
              add version switch for _proc_to_dumpindex
              Debug 3d for old code 
              write code for box to procs to load
     Maybies:
              optimize _pop_particles with  seek to location?


    """

    def __init__(self, 
                 num=None,
                 param_file=None,
                 path='./'): 
        """ Initilazition Routine for dump class 
        """

        self._set_dump_path(path)
        self.param = load_param(param_file)
        self.set_dump_num(num)
        self._set_part_dtype()
        self._tags = False
        if 'mult_species' in self.param:
            self.is_mult_species = True
            raise NotImplementedError()
        else: 
            self.species = ['i','e']
    

    def set_dump_num(self,num):

        choices = glob.glob(self.path+'/p3d-001.*')
        choices = [k[-3:] for k in choices]

        num = _num_to_ext(num)

        if num not in choices:
            
            _ =  'Select from the following possible moive numbers:' \
                 '\n{0} '.format(choices)
            num = int(input(_))
 
        self.num = _num_to_ext(num)

        return None

 
    def read_particles(self,index,wanted_procs=None,tags=False):
        """ #   Method      : read_dump_parts
        """
        
        if tags:
            self._tags = True
        else:
            self._tags = False

        index = _num_to_ext(index)

        F = self._open_dump_file(index)

        self._read_header(F)
        
        if index in self._dump_files_with_fields():
            flds = self._pop_fields(F)

        parts = self._pop_particles(F,wanted_procs)

        if F.read():
            print('ERROR: The entire dump file was not read.\n'\
                  '       Returning what was read.')
        F.close()

        return parts


    def read_fields(self):

        flds = []

        for index in self._dump_files_with_fields():
            F = self._open_dump_file(index)
            self._read_header(F)
            flds += [self._pop_fields(F)]
            F.close()

        fields = flds[0]
        for f in flds[1:]:
            for k in fields:
                fields[k] = np.concatenate((fields[k],f[k]),axis=2)

        return fields


    def _set_dump_path(self, path):
        def get_choices(path):
            choices = glob.glob(path+'/p3d-001.*')
            choices = [k[-3:] for k in choices]
            return choices

        attempt_tol = 5
        path = os.path.abspath(path)
        choices =  get_choices(path)

        c = 0
        while not choices and c < attempt_tol:
            print('='*20 + ' No dump files found ' + '='*20)
            path = os.path.abspath(input('Please Enter Path: '))
            choices =  get_choices(path)
            c =+ 1

        assert choices, 'No dump files found!' 

        self.path = path

        return None


    def _open_dump_file(self,index):

        fname = self.path + '/p3d-{0}.{1}'.format(index,self.num)

        try:
            F = open(fname, "rb")
        except IOError as e:
            print("I/O error({0}): {1}".format(e.errno, e.strerror))
            print("ERROR: Could not open file. " + fname)

        return F


    def _set_part_dtype(self):
        if self.param['prk'] == 4:
            ntype = 'float32'
        elif self.param['prk'] == 8:
            ntype = 'float64'
        else:
            print('prk number {0} not understood!'.format(self.param['prk']))
            raise Exception("Unknown Param Entry")

        self._part_dtype = np.dtype([('x' , ntype), 
                                     ('y' , ntype),
                                     ('z' , ntype),
                                     ('vx', ntype),
                                     ('vy', ntype),
                                     ('vz', ntype)])


    def _pop_fields(self,F):
        """ Reads the fields from a given dump file

            Note: For any 3D system this well get the fields of 
                  px, py and nz where nz is the number z slices 
                  on a dump file which ends up being pez*nz/nchannels
                  But I think they are still sequential

        """

        if self.pz == 1:
            nz = 1
        elif self.pz%self.nchannels == 0:
            nz = self.pz/self.nchannels
        else:
            raise NotImplementedError()

        fields = ['ex','ey','ez','bx','by','bz']

        fdict = {fld : [] for fld in fields}
        
        # This may be somthing that can be set in the param
        dtype = 'float64'
        dtype_size = np.dtype(dtype).itemsize

        for fld in fields:
            for pz in range(nz): 
                for py in range(self.py):
                    pad = self._pop_int(F)
                    fdict[fld].append(np.fromfile(F, dtype=dtype,
                                                  count=int(pad/dtype_size)))
                    self._pop_int(F)
                    #pdb.set_trace()

            #pdb.set_trace()
            fdict[fld] = np.concatenate(fdict[fld])
            fdict[fld] = fdict[fld].reshape(self.px, 
                                            self.py,
                                            nz,
                                            order='F')

            fdict[fld] = fdict[fld].squeeze()

        return fdict


    def _dump_files_with_fields(self):
        pz = self.param['pez']*self.param['nz']
        files_with_fields = ['001']

        for ch in range(1,pz):
            if ch + 1 > self.param['nchannels']:
                break

            files_with_fields.append(_num_to_ext(ch+1))

        return files_with_fields


    def _pop_particles(self, F, wanted_procs=None):
        """ Read the particles from a given dump file F
            and return them.

            N : is the list of procs your want to read from the dump file

            returns pes : a dictonary of species, each species has a list
                          whose elemts are the particles on a given proc
        """
        if self.param['pex']*self.param['pey']*\
            self.param['pez']%self.nchannels != 0:
            raise NotImplementedError()

        nprocs = int(self.param['pex']*self.param['pey']*\
                 self.param['pez']/self.nchannels)
                 
        if wanted_procs is None:
            wanted_procs = list(range(nprocs))

        pes = {} 
        for sp in self.species: 
            pes[sp] = []

            pad = self._pop_int(F)
            n_pes = struct.unpack('<i',F.read(4))[0] 
            self._pop_int(F)

            for n in range(nprocs):

                if n in wanted_procs:
                    pes[sp].append( self._pop_parts_off_grid(F) )
                else:
                    pes[sp].append( self._skip_parts(F) )
                
                # Debuging code that says whwere we are physicaly
                #if sp == 'i':
                #    lpe = [pes[sp][n]['x'].min(),pes[sp][n]['x'].max(),
                #           pes[sp][n]['y'].min(),pes[sp][n]['y'].max(),
                #           pes[sp][n]['z'].min(),pes[sp][n]['z'].max()]

                #    print '[%2.3f, %2.3f, %2.3f, %2.3f, %2.3f, %2.3f]'%tuple(lpe)
        return pes

    def _skip_parts(self,F):

        pad = self._pop_int(F)
        num_parts = self._pop_int(F)
        self._pop_int(F)

        n_bufs = int(np.floor(1.*num_parts/self.bufsize))
        num_parts_last_buf = num_parts - self.bufsize*n_bufs

        if num_parts_last_buf > 0:
            n_bufs += 1
        else:
            # Special case: the number of parts is evenly divisalbe by 
            # bufsize. so we will return the entire last buffer
            num_parts_last_buf = self.bufsize
            print('It is pretty unlikly that we will be here!')

        # Explination of skip size:
        #   x,y,z,vx,vy,vz *prk* particles on a buffer 
        #   tagsize (8)* particles on a buffer
        #   pre and post pad for the parts and tags
        skip_size = 6*self.param['prk']*self.bufsize +\
                    8*self.bufsize +\
                    4*4 
        F.seek(n_bufs*skip_size,1)

        return None

    def _pop_parts_off_grid(self,F):

        pad = self._pop_int(F)
        num_parts = self._pop_int(F)
        self._pop_int(F)

        n_bufs = int(np.floor(1.*num_parts/self.bufsize))
        num_parts_last_buf = num_parts - self.bufsize*n_bufs

        if num_parts_last_buf > 0:
            n_bufs += 1
        else:
            # Special case: the number of parts is evenly divisalbe by 
            # bufsize. so we will return the entire last buffer
            num_parts_last_buf = self.bufsize

        parts = []
        if self._tags: tags = []

        for c in range(n_bufs):

            pad = self._pop_int(F)

            # First we have to read the particle locations and velocties
            # Each particle takes up prk bytes x 6 for (x,y,z,vx,vy,vz)
            parts_on_buf = int(pad/(self.param['prk']*6))

            parts.append( np.fromfile(F, dtype=self._part_dtype, 
                                         count=parts_on_buf))

            self._pop_int(F)

            # Now we need to take care of the tags (if they are there)
            pad = self._pop_int(F)
            if self._tags:
                tags.append(np.fromfile(F, dtype='int64', 
                                        count=parts_on_buf))
            else:
                F.seek(pad,1)

            self._pop_int(F)
        
        parts[-1] = parts[-1][:num_parts_last_buf]

        if self._tags: 
            tags[-1] = tags[-1][:num_parts_last_buf]
            return np.concatenate(parts), \
                   np.concatenate(tags)
        else:
            return np.concatenate(parts)


    def _pop_int(self,F):
        size_of_int = 4
        _ = F.read(size_of_int)
        return struct.unpack('<i',_)[0]


    def _read_header(self,F):

        #if sys.byteorder == 'little': ic = '<' # Littel Endian (do I even need to do this?) 
        #else ic = '>' # Big Endian

        head_size = self._pop_int(F) # Size of the header in bytes
        head = F.read(head_size)

        head = struct.unpack('<dd5i', head) #Double Double, 5 Ints
        self._pop_int(F)

        contents = ['time', 'n_avg', 'px', 'py', 'pz', 'bufsize', 'nchannels']

        dump_vals = {c : h for c,h in zip(contents,head)}

        self._dump_param_consistency_check(dump_vals)

        for c,h in zip(contents,head):
            setattr(self,c,h)

# Maybe make diagnoticts there own class?

    def _dump_param_consistency_check(self,dump_vals):
        
        if not (dump_vals['px'] == self.param['pex']*self.param['nx']):
            raise Exception("Param Dump Consistency Check")
        if not (dump_vals['py'] == self.param['pey']*self.param['ny']):
            raise Exception("Param Dump Consistency Check")
        if not (dump_vals['py'] == self.param['pey']*self.param['ny']):
            raise Exception("Param Dump Consistency Check")
        if not (dump_vals['bufsize'] == self.param['bufsize']):
            raise Exception("Param Dump Consistency Check")
        if not (dump_vals['nchannels'] == self.param['nchannels']):
            raise Exception("Param Dump Consistency Check")

        return True


    def _r0_on_dump_consistency_check(self,r0):

        print('x = {0}, y = {1},  z = {2} '.format(*r0))

        p0 = self._location_to_proc(*r0)

        print('px = {0}, py = {1},  pz = {2} '.format(*p0))

        N,R = self._proc_to_dumpindex(*p0)

        print('N = {0}, R = {1}'.format(N,R))

        try:
            foo = self.read_particles(N)[1]['i'][R]
        except KeyError:
            foo = self.read_particles(N)['i'][R]

        lpe = [foo['x'].min(),foo['x'].max(),
               foo['y'].min(),foo['y'].max(),
               foo['z'].min(),foo['z'].max()]

        err_msg = '{0} = {1} is outside of {0} boundry [{2}, {3}]'
        if r0[0] <= lpe[0] or r0[0] >= lpe[1]:
            raise Exception(err_msg.format('X',r0[0],lpe[0],lpe[1]))
        if r0[1] <= lpe[2] or r0[1] >= lpe[3]:
            raise Exception(err_msg.format('Y',r0[1],lpe[2],lpe[3]))
        if r0[2] <= lpe[4] or r0[2] >= lpe[5]:
            raise Exception(err_msg.format('Z',r0[2],lpe[4],lpe[5]))

