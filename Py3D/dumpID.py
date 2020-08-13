#######################################################################
#                                                                     #
#                  Progs        :  dumpID.py                          #
#                  Aruthor      :  Colby Haggerty                     #
#                  Date         :  2016.01.31                         #
#                                                                     #
#                                                                     #
#######################################################################


import os
import sys
import pdb
import numpy as np
from .dump import Dump
from ._methods import load_param
from ._methods import interp_field
from ._methods import _num_to_ext

class DumpID(object):
    """
        Write better doc strings!

        TODO:  Debug for differnet simulations
                
    """

    def __init__(self, 
                 num=None,
                 param_file=None,
                 path='./'):

        self.dump = Dump(num, param_file, path)
        self.param = self.dump.param


    def get_part_in_box(self,
                        r=[1.,1.],
                        dx=[.5,.5],
                        par=False,
                        species=None,
                        tags=False):
        """ Takes a box defined by its center position r and it's
            widths dx and gets the particle data
        """

        r0  = [1., 1., 0.1]
        dx0 = [.5, .5, self.param['lz']]

        for c,(r_i,dx_i) in enumerate(zip(r,dx)):
            r0[c]  = r_i
            dx0[c] = dx_i

        if species is None:
            parts = {'i':[], 'e':[]}
        else:
            parts = {species:[]}

        if par:
            print('Reading Fields...')
            self.fields = self.dump.read_fields()

        dump_and_index = self._get_procs_in_box(r0[0],dx0[0],
                                                r0[1],dx0[1],
                                                r0[2],dx0[2])

        for d in dump_and_index:
            print('Reading Parts from p3d-{0}.{1}...'.format(d,self.dump.num))
            data = self.dump.read_particles(d,wanted_procs=dump_and_index[d],
                                            tags=tags)

            for sp in parts:
                parts[sp] += [data[sp][g] for g in dump_and_index[d]]

        if tags:
            parts = self._combine_parts_and_tags(parts)

        for sp in parts:
            for c,p in enumerate(parts[sp]):
                print('  Triming {0} from {1}...'.format(sp,c))
                parts[sp][c] = self._trim_parts(p, r0, dx0)

            parts[sp] = np.hstack(parts[sp])
            if par:
                parts[sp] = self._rotate_parts(parts[sp], r0, dx0)

        if len(list(parts.keys())) == 1:
            parts = parts[list(parts.keys())[0]]

        return parts


    def _combine_parts_and_tags(self,parts):
        """ Merge the particle tags and phase space values
            
            There is a small chance that this may be slow!
            So maybe come back and try to fix it? if it needs it
        """
        bind_parts = {}
        for sp in parts:
            part_dtype = parts[sp][0][0].dtype.descr
            tag_dtype = [('tag',parts[sp][0][1].dtype)]
            new_dtype = np.dtype(part_dtype + tag_dtype)

            bind_parts[sp] = []
            for g, (phase_space, tags) in enumerate(parts[sp]): 
                pts = np.empty(np.size(phase_space), dtype = new_dtype)
                for fld in pts.dtype.fields:
                    if fld == 'tag':
                        pts[fld] = tags
                    else:
                        pts[fld] = phase_space[fld]

                bind_parts[sp].append(pts)

        return bind_parts

    def _rotate_parts(self, p0, r0, dx0):
        b0,e0 = self._interp_fields(r0)

        exb = np.cross(b0,e0)
        exb = exb/np.sqrt(np.sum(exb**2))

        bbb = b0/np.sqrt(np.sum(b0**2))

        beb = np.cross(bbb,exb)
        
        ntype = p0.dtype.descr[3][1] #This is the type of vx

        extra_dt = [('v0', ntype),
                    ('v1', ntype),
                    ('v2', ntype)]

        new_dt = np.dtype(p0.dtype.descr + extra_dt)

        p1 = np.zeros(p0.shape,dtype=new_dt)

        for v in ['x', 'y', 'z', 'vx', 'vy', 'vz']:
            p1[v] = p0[v]
       
        for v,ehat in zip(('v0','v1','v2'),(bbb,exb,beb)):
            p1[v] = ehat[0]*p0['vx'] + ehat[1]*p0['vy'] + ehat[2]*p0['vz']

        return p1


    def _interp_fields(self, r0):

        if self._is_2D():
            sim_lens = [self.param['l'+v] for v in ['x','y']]
            r0 = r0[:2]

        else:
            sim_lens = [self.param['l'+v] for v in ['x','y','z']]
            r0 = r0[:3]


        b0 = np.empty(3)
        e0 = np.empty(3)

        for g,fld in enumerate(['bx','by','bz']):
            b0[g] = interp_field(self.fields[fld],r0,sim_lens)

        for g,fld in enumerate(['ex','ey','ez']):
            e0[g] = interp_field(self.fields[fld],r0,sim_lens)

        return b0,e0
        #bx_intp = interp_field()
        #raise NotImplementedError()


    def _trim_parts(self, p0, r0, dx0):

        if self._is_2D():
            vrng = ['x','y']
        else:
            vrng = ['x','y','z']
        
        for c,v in enumerate(vrng):
            to_mask = np.where((r0[c] - dx0[c]/2. <= p0[v]) & \
                               (p0[v] <= r0[c] + dx0[c]/2.))
            p0 = p0[to_mask]

        return p0

    def _is_2D(self):
        if self.param['pez']*self.param['nz'] == 1:
            return True
        else:
            return False 


    def _get_procs_in_box(self, x0, dx, y0, dy, z0, dz):
        """
        Takes the real r postion and returns what dump file
        partilces coresponding to that position will be on, as well as
        the index position of the list of processeors on that dump file.

        """

        proc_dx = np.array([self.param['lx']/self.param['pex'],
                            self.param['ly']/self.param['pey'],
                            self.param['lz']/self.param['pez']])

        r0 = np.array([x0,y0,z0])
        dx = np.array([dx,dy,dz])

        procs_needed = [] # The corners of the cube 
        
        # find the lower left most proc
        procs_needed.append(self._r0_to_proc(*(r0 - dx/2.)))
         
        r0_rng = []
        for c in range(3):
            r0_rng.append(np.arange(r0[c] - dx[c]/2., 
                                    r0[c] + dx[c]/2.,
                                    proc_dx[c]))

            if r0_rng[c][-1] < r0[c] + dx[c]/2.:
                r0_rng[c] = np.hstack((r0_rng[c],r0[c] + dx[c]/2.))

        print(r0_rng)

        p0_rng = []
        for x in r0_rng[0]:
            for y in r0_rng[1]:
                for z in r0_rng[2]:
                    p0_rng.append(self._r0_to_proc(x,y,z))

        p0_rng = set(p0_rng) #This removes duplicates

        di_dict = {}
        for p in p0_rng:
            d = self._proc_to_dumplocation(*p)
            if d[0] in di_dict:
                di_dict[d[0]].append(d[1])
            else:
                di_dict[d[0]] = [d[1]]

        for k in di_dict:
            di_dict[k].sort()
            di_dict[k] = list(set(di_dict[k]))
            #print k, di_dict[k]

        return di_dict


    def _r0_to_proc(self, x0, y0, z0):
        """ Returns the px,py,pz processeor for a given values of x, y, and z
        """

        lx = self.param['lx']
        ly = self.param['ly']
        lz = self.param['lz']
        
        err_msg = '{0} value {1} is outside of the simulation boundry [0.,{2}].'+\
                  'Setting {0} = {3}'

        if x0 < 0.:
            print(err_msg.format('X',x0,lx,0.))
            px = 1
        elif x0 >= lx:
            print(err_msg.format('X',x0,lx,lx))
            px = self.param['pex']
        else:
            px = int(np.floor(x0/self.param['lx']*self.param['pex'])) + 1

        if y0 < 0.:
            print(err_msg.format('Y',y0,ly,0.))
            py = 1
        elif y0 >= ly:
            print(err_msg.format('Y',y0,ly,ly))
            py = self.param['pey']
        else:
            py = int(np.floor(y0/self.param['ly']*self.param['pey'])) + 1

        if self._is_2D():
            pz = 1
        else:
            if z0 < 0.:
                print(err_msg.format('Z',z0,lz,0.))
                pz = 1
            elif z0 >= lz:
                print(err_msg.format('Z',z0,lz,lz))
                pz = self.param['pez']
            else:
                pz = int(np.floor(z0/self.param['lz']*self.param['pez'])) + 1

        return px,py,pz


    def _proc_to_dumplocation(self, px, py, pz):
        """ Returns the dump index (di), as well as the postion in the array 
            returned in _get_particles(dump_index=di)

        Big Note: There are two ways marc stores procs on dump files:
                  an old way and a new way. We need a to distingush
                  which way we are using.
        Old Way:
            Scan over Y, Scan over X then Scan over Z
        New Way:
            Scan over X, Scan over Y then Scan over Z
        """

        pex = self.param['pex']
        pey = self.param['pey']
        pez = self.param['pez']
        nch = self.param['nchannels']

        if pex*pey*pez%nch != 0:
            raise NotImplementedError()

        dump_IO_version = 'V1'

        if 'USE_IO_V2' in self.param:
            dump_IO_version = 'V2'
       
        if dump_IO_version == 'V1':
            print('Using IO V1...')
            N = (px - 1)%nch + 1
            R = (pz - 1)*(pex/nch)*(pey) + (pex/nch)*(py - 1) + (px - 1)/nch

        else: # dump_IO_version == 'V2'
            print('Using IO V2...')

            npes_per_dump = pex*pey*pez/nch

            pe = (pz - 1)*pex*pey + (py - 1)*pex + (px - 1)
            
            N = pe/npes_per_dump + 1
            R = pe%npes_per_dump

        return _num_to_ext(N),R



