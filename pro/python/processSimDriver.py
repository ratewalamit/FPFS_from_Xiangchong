#!/usr/bin/env python
#
# LSST Data Management System
# Copyright 20082014 LSST Corporation.
#
# This product includes software developed by the
# LSST Project (http://www.lsst.org/).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.
#
# You should have received a copy of the LSST License Statement and
# the GNU General Public License along with this program.  If not,
# see <http://www.lsstcorp.org/LegalNotices/>.
#
# python lib
import os
import galsim
import numpy as np
import astropy.io.fits as pyfits

# lsst Tasks
import lsst.daf.base as dafBase
import lsst.pex.config as pexConfig
import lsst.pipe.base as pipeBase
import lsst.afw.math as afwMath
import lsst.afw.table as afwTable
import lsst.afw.image as afwImg
import lsst.afw.detection as afwDet
import lsst.afw.geom as afwGeom
import lsst.afw.coord as afwCoord

from lsst.pipe.base import TaskRunner
from lsst.ctrl.pool.parallel import BatchPoolTask
from lsst.ctrl.pool.pool import Pool, abortOnError

import lsst.obs.subaru.filterFraction
from fpfsBase import fpfsBaseTask
from readDataSim import readDataSimTask

class processSimConfig(pexConfig.Config):
    "config"
    readDataSim= pexConfig.ConfigurableField(
        target  = readDataSimTask,
        doc     = "Subtask to run measurement of fpfs method"
    )
    fpfsBase = pexConfig.ConfigurableField(
        target = fpfsBaseTask,
        doc = "Subtask to run measurement of fpfs method"
    )
    def setDefaults(self):
        pexConfig.Config.setDefaults(self)
        self.fpfsBase.doTest=   False
        self.fpfsBase.doFD  =   False
        self.fpfsBase.dedge =   2

class processSimTask(pipeBase.CmdLineTask):
    _DefaultName = "processSim"
    ConfigClass = processSimConfig
    def __init__(self,**kwargs):
        pipeBase.CmdLineTask.__init__(self, **kwargs)
        self.schema     =   afwTable.SourceTable.makeMinimalSchema()
        self.makeSubtask("readDataSim",schema=self.schema)        
        self.makeSubtask('fpfsBase', schema=self.schema)
        
        
    @pipeBase.timeMethod
    def run(self,ifield):
        index       =   ifield//8
        ig          =   ifield%8
        prepend     =   '-id%d-g%d' %(index,ig)
        self.log.info('start index: %d, shear: %d' %(index,ig))
        inputdir    =   './rgc/expSim/' 
        inFname     =   os.path.join(inputdir,'image%s.fits' %(prepend))
        if not os.path.exists(inFname):
            self.log.info('Cannot find the input exposure')
            return
        outputdir   =   './rgc/outcomeFPFS/' 
        if not os.path.exists(outputdir):
            os.mkdir(outputdir)
        outFname    =   'src%s.fits' %(prepend)
        outFname    =   os.path.join(outputdir,outFname)
        if os.path.exists(outFname):
            self.log.info('Already have the output file')
            return
        dataStruct  =   self.readDataSim.readData(prepend)
        if dataStruct is None:
            self.log.info('failed to read data')
            return
        else:
            self.log.info('successed in reading data')
        self.fpfsBase.run(dataStruct)
        dataStruct.sources.writeFits(outFname,flags=afwTable.SOURCE_IO_NO_FOOTPRINTS)
        return
    
    @classmethod
    def _makeArgumentParser(cls):
        """Create an argument parser
        """
        parser = pipeBase.ArgumentParser(name=cls._DefaultName)
        return parser

    def writeConfig(self, butler, clobber=False, doBackup=False):
        pass

    def writeSchemas(self, butler, clobber=False, doBackup=False):
        pass

    def writeMetadata(self, ifield):
        pass

    def writeEupsVersions(self, butler, clobber=False, doBackup=False):
        pass
        

class processSimDriverConfig(pexConfig.Config):
    minField =   pexConfig.Field(dtype=int, default=0, doc = 'minField')
    maxField =   pexConfig.Field(dtype=int, default=1, doc = 'minField')
    processSim = pexConfig.ConfigurableField(
        target = processSimTask,
        doc = "processSim task to run on multiple cores"
    )
    def setDefaults(self):
        pexConfig.Config.setDefaults(self)

class processSimRunner(TaskRunner):
    @staticmethod
    def getTargetList(parsedCmd, **kwargs):
        return [(ref, kwargs) for ref in range(1)] 

def unpickle(factory, args, kwargs):
    """Unpickle something by calling a factory"""
    return factory(*args, **kwargs)

class processSimDriverTask(BatchPoolTask):
    ConfigClass = processSimDriverConfig
    RunnerClass = processSimRunner
    _DefaultName = "processSimDriver"
    
    def __reduce__(self):
        """Pickler"""
        return unpickle, (self.__class__, [], dict(config=self.config, name=self._name,
                parentTask=self._parentTask, log=self.log))

    def __init__(self,**kwargs):
        BatchPoolTask.__init__(self, **kwargs)
        self.makeSubtask("processSim")
    
    @abortOnError
    def run(self,Id):
        # Get the  galaxy generator      
        # Load data
        #Prepare the pool
        pool    =   Pool("processSim")
        pool.cacheClear()
        fieldList=  range(self.config.minField,self.config.maxField)
        pool.map(self.process,fieldList)
        return
        
    def process(self,cache,ifield):
        self.processSim.run(ifield)
        self.log.info('finish field %03d' %(ifield))
        return

    @classmethod
    def _makeArgumentParser(cls, *args, **kwargs):
        kwargs.pop("doBatch", False)
        parser = pipeBase.ArgumentParser(name=cls._DefaultName)
        return parser
    
    @classmethod
    def batchWallTime(cls, time, parsedCmd, numCpus):
        return None

    def writeConfig(self, butler, clobber=False, doBackup=False):
        pass

    def writeSchemas(self, butler, clobber=False, doBackup=False):
        pass
    
    def writeMetadata(self, ifield):
        pass
    
    def writeEupsVersions(self, butler, clobber=False, doBackup=False):
        pass
    
    def _getConfigName(self):
        return None
   
    def _getEupsVersionsName(self):
        return None
    
    def _getMetadataName(self):
        return None