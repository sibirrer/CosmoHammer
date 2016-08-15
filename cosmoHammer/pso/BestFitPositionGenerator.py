'''
Created on Oct 22, 2013

@author: J.Akeret
'''
from __future__ import print_function, division, absolute_import, unicode_literals

import numpy
from cosmoHammer.pso.ParticleSwarmOptimizer import ParticleSwarmOptimizer
from cosmoHammer.pso.CurvatureFitter import CurvatureFitter

class BestFitPositionGenerator(object):
    '''
    A position generator which uses a particle swarm optimization algorithm 
    to find the best fit value and the collapsed swarm to estimate the curvature matrix
    at that point. The optimization process can be parallelized over
    MPI and python multiprocessing.
    
    :param mpi: True if a MPI implementation of the PSO should be used. Default is False 
    :param threads: Number of multiprocessing thread that should be started. Default is 1
    :param particleCount: Number of particle to use for the optimization. If none 
        the number is derrived according to the size of the parameter space. Default is None
    :param maxIter: the maximal number of iterations. Default will be set to MAX_PSO_ITER
    
    '''
    
    MAX_PSO_ITER = 1000
    
    MIN_PARTICLE_COUNT = 20
    
    BEST_FILE_NAME = "_best_fit_global.out"

    BEST_INFO_FILE_NAME = "_best_fit_info.out"

    def __init__(self, mpi=False, threads=1, particleCount=None, maxIter=None):
        """
            default constructor
        """
        self.mpi = mpi
        self.threads = threads
        self.particleCount = particleCount
        
        self.maxIter = maxIter
        if(self.maxIter is None):
            self.maxIter = self.MAX_PSO_ITER
        

    def setup(self, sampler):
        """
        setup the generator
        """
        self.sampler = sampler
        
    def generate(self):
        """
        generates the positions by running the PSO and using the chain's min and max and then calling 
        the paraboloid fitter in order to estimate the covariance matrix. The position will then
        be generated by drawing position from a multivariant gaussian distribution defined by
        the best fit and the estimated covariance matrix.
        The progress of the PSO is successively stored to a the disk.
        """
        
        chain = self.sampler.likelihoodComputationChain
        
        if(self.particleCount is None):
            self.particleCount = self.get_particle_count()

        if(self.mpi):
            #only import when needed in order to avoid an error in case mpi4py is not installed
            from cosmoHammer.sampler.util.pso.MpiParticleSwarmOptimizer import MpiParticleSwarmOptimizer
            
            pso = MpiParticleSwarmOptimizer(chain, chain.min, chain.max, self.particleCount, threads=self.threads)
        else:
            pso = ParticleSwarmOptimizer(chain, chain.min, chain.max, self.particleCount, threads=self.threads)
        
        swarm = []
        with open(self.sampler.filePrefix+self.BEST_FILE_NAME, "w") as f:
            for i, cswarm in enumerate(pso.sample(self.maxIter)):
                self._save(f, i, pso)
                if(i>=0):
                    swarm.append(cswarm)

            self._save(f, i+1, pso)
        self.sampler.log("Best fit found after %s iteration: %f %s"%(i+1, pso.gbest.fitness, pso.gbest.position))
        
        
        fswarm = []
        for i in range(1,5):
            fswarm += swarm[-i]

        self._storeSwarm(fswarm)
        
        fitter = CurvatureFitter(fswarm, pso.gbest)
        mean, _cov = fitter.fit()
        
        self._storeFit(pso.gbest, _cov)

#         dim = len(mean)-1
#         sigma = 0.4
#         factor = _cov[dim,dim] / numpy.sqrt(sigma)
#         _cov[:-1,dim] = _cov[:-1,dim]/factor
#         _cov[dim,:-1] = _cov[dim,:-1]/factor
#         _cov[dim,dim] = sigma
#         print ""
#         fitter = ParaboloidFitter(fswarm, pso.gbest, True)
#         mean, _cov = fitter.fit()
        sigma = numpy.sqrt(numpy.diag(_cov))
        print("=> found sigma:", sigma)
        
#        fitter = ParaboloidFitter(pso.swarm, pso.gbest)
#        mean, _cov = fitter.fit()
#        sigma = numpy.sqrt(numpy.diag(_cov))
#        print "=> found sigma:", sigma
        
        samples = numpy.random.multivariate_normal(mean, _cov, self.sampler.nwalkers)
#         print numpy.std(samples, axis=0)
        return samples
        
#         self.sampler.paramValues = pso.gbest.position
#         self.sampler.paramWidths = self.sampler.paramValues * self.SPREAD_FACTOR
#         generator = SampleBallPositionGenerator()
#         generator.setup(self.sampler)
#         return generator.generate()

        
        
    
    def get_particle_count(self):
        """
        Generates the number of particles to use by using a logarithmic function of the parameter count
        """
        return int(self.MIN_PARTICLE_COUNT + self.MIN_PARTICLE_COUNT*numpy.log(self.sampler.paramCount))
    
    def __str__(self, *args, **kwargs):
        return "BestFitPositionGenerator: particleCount=%s, mpi=%s, threads=%s"%(self.particleCount, self.mpi, self.threads)
    
    def _save(self, f, i, pso):
        if(pso.isMaster()):
            particle = pso.gbest
            f.write("%s\t%f\t"%(i, particle.fitness))
            f.write("\t".join([str(p) for p in particle.position]))
            f.write("\n")
            f.flush()
                        
    def _storeFit(self, gbest, _cov):
        with open(self.sampler.filePrefix+self.BEST_INFO_FILE_NAME, "w") as f:
            f.write("#Best fit: %s\n"%(gbest.fitness))
            f.write(", ".join([str(i) for i in gbest.position]))
            f.write("\n#Estimated covariance matrix:\n")
            for row in _cov:
                f.write ("[" + ",  ".join([str(i) for i in row]) + "]\n")

    def _storeSwarm(self, swarm):
        with open(self.sampler.filePrefix+"swarm", "w") as f:
            for particle in swarm:
                f.write(str(particle.fitness))
                f.write("\t")
                f.write("\t".join([str(p) for p in particle.position]))
                f.write("\n")