import os
import pdb
import glob
import numpy as np
from ._methods import load_param
from ._methods import _num_to_ext

class Movie(object):
    """Class to load p3d movie data"""

    def __init__(self,
                 num=None,
                 param=None,
                 path='./'):
        """ Initlize a movie object
        """
        print(path)
        print(param)
        self._name_sty  = '/movie.{0}.{1}'
        self.path       = self._get_movie_path(path)
        if param is not None: param = self.path + '/' + param
        print(param)
        self.param      = load_param(param)
        self.num        = self._get_movie_num(num)
        self.movie_vars = self._get_movie_vars()
        self.log        = self._load_log()
        self.ntimes     = len(self.log[self.movie_vars[0]])


    def get_fields(self, vars, time=None):
        """ Loads the field(s) var at for a given time(s)

            var can be:
                a string field name
                a sequence of string field names
                or simply 'all'
        """

        if 'all' in vars:
            vars = tuple(self.movie_vars)
        elif type(vars) is str:
            vars = [vars]

        flds = {} 
        for v in vars:
            if v not in self.movie_vars:
                err_msg = 'var {0} not found in posible field values.\n{1}'
                err_msg = err_msg.format(v,self.movie_vars)
                raise KeyError(err_msg)

            flds[v] = self._read_movie(v,time)
        
        
        xyz_vecs = self._get_xy_vectors()
        for k in xyz_vecs:
            flds[k] = xyz_vecs[k]

        return flds

    def _get_xy_vectors(self):
        xyz_vecs = {}

        dx = self.param['lx']/(self.param['pex']*self.param['nx'])
        xyz_vecs['xx'] = np.arange(dx/2.,self.param['lx'],dx)

        dy = self.param['ly']/(self.param['pey']*self.param['ny'])
        xyz_vecs['yy'] = np.arange(dy/2.,self.param['ly'],dy)

        if self.param['pez']*self.param['nz'] > 1:
            dz = self.param['lz']/(self.param['pez']*self.param['nz'])
            xyz_vecs['zz'] = np.arange(dz/2.,self.param['lz'],dz)

        return xyz_vecs
#        if type(var) is not list:
#            if var.lower() == 'all': var_arr = self.movie_arr
#            else: var_arr = [var]
#        else: var_arr = var
#        return_dict = {}
#        for cosa in var_arr:
#            if (cosa not in self.movie_arr):
#                print 'Varable %s not found in movie_arr. Nothing was loaded!'%cosa
#                cosa = raw_input('Please Enter a Varible: ')
#            if (cosa not in self.movie_arr):
#                print 'Varable %s not found in movie_arr. Nothing was loaded!'%cosa
#                print 'You dont get a second try!'
#                return -1
#
#            if time is None:
#                time = raw_input('Time %s out of range [0 - %i]\n'% \
#                                 (time,self.num_of_times-1) + \
#                                 'Please Enter a time: ')
#
#            if time == 'all':
#                time = range(self.num_of_times)
#            elif type(time) == str:
#                time = [int(x) for x in time.split()]
#            elif type(time) is int:
#                time = [time]
#            else:
#                time = list(time)
#
#            for chose in time:
#                if -1 < chose < self.num_of_times:
#                    pass
#                else:
#                    print 'Time %i is out of time range [%i - %i]'\
#                          %(chose,0,self.num_of_times-1)
#                    return None
#
#            fname = self.movie_path+'/movie.'+cosa+'.'+self.movie_num_str
#            fname = os.path.abspath(fname)

    def _read_movie(self,var, time):
        
        # Insert Comment about werid movie shape
        movie_shape = (self.ntimes,
                       self.param['pez']*self.param['nz'],
                       self.param['pey']*self.param['ny'],
                       self.param['pex']*self.param['nx'])
        

        fname = self.path + self._name_sty.format(var,self.num)
        print("Loading {0}".format(fname))

        # It seems that Marc Swisdak hates us and wants to be unhappy because 
        # the byte data is unsigned and the doulbe byte is signed so that is 
        # why one has a uint and the other is just int
        if 'double_byte' in self.param:
            dat_type = np.dtype('int16')
            norm = 256**2-1
            shft = 1.0*256**2/2
        else: #single byte precision
            dat_type = np.dtype('uint8')
            norm = 256-1
            shft = 0.0

        t = 0 # This keeps track of where we are
        cmin = self.log[var][:,0][time]
        cmax = self.log[var][:,1][time]

        mov = np.memmap(fname, dtype=dat_type, mode='r', shape=movie_shape)

        mov = mov[time].view(np.ndarray)
        mov = (1.*mov.T + shft)*(cmax - cmin)/(1.0*norm) + cmin 
        mov = np.squeeze(mov)
        return mov


    def _load_log(self):
        """ Loads the log file for a given set of moives files
            It creates a dictoary 
        """

        fname = self.path + self._name_sty.format('log', self.num)

        print("Loading {0}".format(fname))
        clims = np.loadtxt(fname)
        
        if len(clims)%len(self.movie_vars) != 0:
            raise Exception('Param/Moive Incompatibility')

        log = {}
        num_of_vars = len(self.movie_vars)
        for c,k in enumerate(self.movie_vars):
            log[k] = clims[c::num_of_vars,:]
    
        return log
        # usefull use later
        #print "movie.log '%s' has %i time slices"%(fname,self.num_of_times)

# STRUCTURE OF movie_log_dict{}
#   movie_log_dict is a dictionary of all the of the varibles that could be read in a movie file
#   you pass the standered name of the varible as a string and you get back an array.
#   in the array each element coresponds to a diffrent time slice
#   so      movie.movie_log_dict['bz'] = [


    def _get_movie_path(self,path):

        attempt_tol = 5
        path = os.path.abspath(path)
        choices = glob.glob(path + self._name_sty.format('log', '*'))

        c = 0
        while not choices and c < attempt_tol:
            print('='*20 + ' No movie files found ' + '='*20)
            path = os.path.abspath(input('Please Enter Path: '))
            c =+ 1

        assert choices, 'No movie log files found!' 

        return path


    def _get_movie_num(self,num):

        choices = glob.glob(self.path + self._name_sty.format('log', '*'))
        choices = [k[-3:] for k in choices]

        num = _num_to_ext(num)

        if num not in choices:
            _ =  'Select from the following possible moive numbers:'\
                 '\n{0}'.format(choices)
            num = int(input(_))
 
        return _num_to_ext(num)


    def _get_movie_vars(self):
        #NOTE: The movie_vars are in an order, please do not switch around 
        #      unless you want incidious bugs

        #Check the moive header type
        if self.param['movie_header'] == '"movie2dC.h"':
            return ['rho',
                    'jx','jy','jz',
                    'bx','by','bz',
                    'ex','ey','ez',
                    'ne',
                    'jex','jey','jez',
                    'pexx','peyy','pezz','pexy','peyz','pexz',
                    'ni',
                    'pixx','piyy','pizz','pixy','piyz','pixz']

        elif self.param['movie_header'] == '"movie4b.h"':
            return ['rho',
                    'jx','jy','jz',
                    'bx','by','bz',
                    'ex','ey','ez',
                    'ne','jex','jey','jez',
                    'pexx','peyy','pezz','pexz','peyz','pexy',
                    'ni','jix','jiy','jiz',
                    'pixx','piyy','pizz' 'pixz','piyz','pixy']

        elif self.param['movie_header'] == '"movie2dD.h"':
            return ['rho',
                    'jx','jy','jz',
                    'bx','by','bz',
                    'ex','ey','ez',
                    'ne',
                    'jex','jey','jez',
                    'pexx','peyy','pezz','pexy','peyz','pexz',
                    'ni',
                    'jix','jiy','jiz',
                    'pixx','piyy','pizz','pixy','piyz','pixz']

        elif self.param['movie_header'] == '"movie3dHeat.h"':
            return ['rho',
                    'jx','jy','jz',
                    'bx','by','bz',
                    'ex','ey','ez',
                    'ne',
                    'jex','jey','jez',
                    'pexx','peyy','pezz','pexy', 'peyz', 'pexz',
                    'ni',
                    'pixx','piyy','pizz','pixy', 'piyz', 'pixz',
                    'epar1','epar2','epar3',
                    'eperp1','eperp2','eperp3',
                    'vpar1','vpar2','vpar3']

        elif self.param['movie_header'] == '"movie_pic3.0.h"':
            return ['rho',
                    'jx','jy','jz',
                    'bx','by','bz',
                    'ex','ey','ez',
                    'ne',
                    'jex','jey','jez',
                    'pexx','peyy','pezz','pexy','peyz','pexz',
                    'ni',
                    'jix','jiy','jiz',
                    'pixx','piyy','pizz','pixy','piyz','pixz']
 
        else:
            err_msg = '='*80 + \
                      '\t This particular moive headder has not been coded!\n'\
                      '\tTalk to Colby to fit it, or fix it yourself.\n'\
                      '\tI dont care, Im a computer not a cop'\
                      '='*80

            print(err_msg)
            raise NotImplementedError()

################################################################################
############   Any thing below here has not been added yet  ####################
################################################################################

#c##Colby you need to figure out a way to make sure that
#c## the path is ok this should likly be done one level up.
#c#
#c#
#c#
#c#
#c##---------------------------------------------------------------------------------------------------------------
#c##   Method: load_movie
#c##   Args  : movie_num (to identify which of the posible several movie files to read from)
#c##         : movie_var (to identify which varible you want to read)
#c##         : movie_time (to identify which slice of time should be read)
#c##       This accepts the run name idetifies the coresponding
#c##       information in the run_list.dat file.
#c##---------------------------------------------------------------------------------------------------------------
#c#
#c#
#c#
#c#
#c#    def get_domain_arrays(self):
#c#        lx = self.param_dict['lx']
#c#        ly = self.param_dict['ly']
#c#        nx = self.param_dict['pex']*self.param_dict['nx']
#c#        ny = self.param_dict['pey']*self.param_dict['ny']
#c#        dx = lx/nx
#c#        dy = ly/ny
#c#        return (np.arange(dx/2.,lx,dx),np.arange(dy/2.,ly,dy))


class UnfinishedMovie(Movie):
    """Class to load p3d movie data"""

    def __init__(self, param=None):
        """ Initlize a movie object
        """
        self._name_sty  = '/{0}'
        self.path       = './'
        self.param      = load_param(param)
        self.num        = '999'
        self.movie_vars = self._get_movie_vars()
        self.log        = self._load_log()
        self.ntimes     = len(self.log[self.movie_vars[0]])


def load_movie(vars=None, time=None, movie_num=None):
    param = glob.glob('./param*')

    M = Movie(param=param, num=movie_num)

    if time is None:
        get_time_msg = 'There are {0} times in movie number {1}. \n' +\
                       'Please enter the time: '

        get_time_msg = get_time_msg.format(M.ntimes, M.num)

        time = -1 
        attempt_tol = 5
        ctr = 0
        while time not in list(range(M.ntimes)) and ctr < attempt_tol:
            time = input(get_time_msg)
            ctr =+ 1
    #return 
