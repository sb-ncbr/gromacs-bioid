"""
 utility functions with "chemical know-how"

"""
from __future__ import annotations
import os as os
from rdkit import RDConfig
import re as re
__all__ = ['ConfigToNumElectrons', 'GetAtomicData', 'RDConfig', 'SplitComposition', 'os', 're']
def ConfigToNumElectrons(config, ignoreFullD = 0, ignoreFullF = 0):
    """
     counts the number of electrons appearing in a configuration string
    
          **Arguments**
    
            - config: the configuration string (e.g. '2s^2 2p^4')
    
            - ignoreFullD: toggles not counting full d shells
    
            - ignoreFullF: toggles not counting full f shells
    
          **Returns**
    
            the number of valence electrons
    
        
    """
def GetAtomicData(atomDict, descriptorsDesired, dBase = '/project/build/temp.linux-x86_64-cpython-311/rdkit_install/share/RDKit/Data/atomdb.gdb', table = 'atomic_data', where = '', user = 'sysdba', password = 'masterkey', includeElCounts = 0):
    """
     pulls atomic data from a database
    
          **Arguments**
    
            - atomDict: the dictionary to populate
    
            - descriptorsDesired: the descriptors to pull for each atom
    
            - dBase: the DB to use
    
            - table: the DB table to use
    
            - where: the SQL where clause
    
            - user: the user name to use with the DB
    
            - password: the password to use with the DB
    
            - includeElCounts: if nonzero, valence electron count fields are added to
               the _atomDict_
    
        
    """
def SplitComposition(compStr):
    """
     Takes a simple chemical composition and turns into a list of element,# pairs.
    
            i.e. 'Fe3Al' -> [('Fe',3),('Al',1)]
    
            **Arguments**
    
             - compStr: the composition string to be processed
    
            **Returns**
    
             - the *composVect* corresponding to _compStr_
    
            **Note**
    
              -this isn't smart enough by half to deal with anything even
                  remotely subtle, so be gentle.
    
        
    """
_atomDbName: str = '/project/build/temp.linux-x86_64-cpython-311/rdkit_install/share/RDKit/Data/atomdb.gdb'
