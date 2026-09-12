from __future__ import annotations
import copy as copy
import math as math
import numpy as numpy
from rdkit import Chem
from rdkit.Chem import Draw
from rdkit.Chem.Draw import rdMolDraw2D
from rdkit.Chem import rdDepictor
from rdkit.Chem import rdMolDescriptors as rdMD
from rdkit import DataStructs
from rdkit import Geometry
__all__ = ['Chem', 'DataStructs', 'Draw', 'Geometry', 'GetAPFingerprint', 'GetAtomicWeightsForFingerprint', 'GetAtomicWeightsForModel', 'GetMorganFingerprint', 'GetRDKFingerprint', 'GetSimilarityMapForFingerprint', 'GetSimilarityMapForModel', 'GetSimilarityMapFromWeights', 'GetStandardizedWeights', 'GetTTFingerprint', 'apDict', 'cm', 'copy', 'math', 'numpy', 'rdDepictor', 'rdMD', 'rdMolDraw2D', 'ttDict']
def GetAPFingerprint(mol, atomId = -1, fpType = 'normal', nBits = 2048, minLength = 1, maxLength = 30, nBitsPerEntry = 4, **kwargs):
    """
    
        Calculates the atom pairs fingerprint with the torsions of atomId removed.
    
        Parameters:
          mol -- the molecule of interest
          atomId -- the atom to remove the pairs for (if -1, no pair is removed)
          fpType -- the type of AP fingerprint ('normal', 'hashed', 'bv')
          nBits -- the size of the bit vector (only for fpType='bv')
          minLength -- the minimum path length for an atom pair
          maxLength -- the maxmimum path length for an atom pair
          nBitsPerEntry -- the number of bits available for each pair
        
    """
def GetAtomicWeightsForFingerprint(refMol, probeMol, fpFunction, metric = ...):
    """
    
        Calculates the atomic weights for the probe molecule
        based on a fingerprint function and a metric.
    
        Parameters:
          refMol -- the reference molecule
          probeMol -- the probe molecule
          fpFunction -- the fingerprint function
          metric -- the similarity metric
    
        Note:
          If fpFunction needs additional parameters, use a lambda construct
        
    """
def GetAtomicWeightsForModel(probeMol, fpFunction, predictionFunction):
    """
    
        Calculates the atomic weights for the probe molecule based on
        a fingerprint function and the prediction function of a ML model.
    
        Parameters:
          probeMol -- the probe molecule
          fpFunction -- the fingerprint function
          predictionFunction -- the prediction function of the ML model
        
    """
def GetMorganFingerprint(mol, atomId = -1, radius = 2, fpType = 'bv', nBits = 2048, useFeatures = False, **kwargs):
    """
    
        Calculates the Morgan fingerprint with the environments of atomId removed.
    
        Parameters:
          mol -- the molecule of interest
          radius -- the maximum radius
          fpType -- the type of Morgan fingerprint: 'count' or 'bv'
          atomId -- the atom to remove the environments for (if -1, no environments is removed)
          nBits -- the size of the bit vector (only for fpType = 'bv')
          useFeatures -- if false: ConnectivityMorgan, if true: FeatureMorgan
    
        any additional keyword arguments will be passed to the fingerprinting function.
        
    """
def GetRDKFingerprint(mol, atomId = -1, fpType = 'bv', nBits = 2048, minPath = 1, maxPath = 5, nBitsPerHash = 2, **kwargs):
    """
    
        Calculates the RDKit fingerprint with the paths of atomId removed.
    
        Parameters:
          mol -- the molecule of interest
          atomId -- the atom to remove the paths for (if -1, no path is removed)
          fpType -- the type of RDKit fingerprint: 'bv'
          nBits -- the size of the bit vector
          minPath -- minimum path length
          maxPath -- maximum path length
          nBitsPerHash -- number of to set per path
        
    """
def GetSimilarityMapForFingerprint(refMol, probeMol, fpFunction, draw2d, metric = ..., **kwargs):
    """
    
        Generates the similarity map for a given reference and probe molecule,
        fingerprint function and similarity metric.
    
        Parameters:
          refMol -- the reference molecule
          probeMol -- the probe molecule
          fpFunction -- the fingerprint function
          metric -- the similarity metric.
          kwargs -- additional arguments for drawing
        
    """
def GetSimilarityMapForModel(probeMol, fpFunction, predictionFunction, draw2d, **kwargs):
    """
    
        Generates the similarity map for a given ML model and probe molecule,
        and fingerprint function.
    
        Parameters:
          probeMol -- the probe molecule
          fpFunction -- the fingerprint function
          predictionFunction -- the prediction function of the ML model
          kwargs -- additional arguments for drawing
        
    """
def GetSimilarityMapFromWeights(mol, weights, draw2d, colorMap = None, scale = -1, size = (250, 250), sigma = None, coordScale = 1.5, step = 0.01, colors = 'k', contourLines = 10, alpha = 0.5, **kwargs):
    """
    
        Generates the similarity map for a molecule given the atomic weights.
    
        Parameters:
          mol -- the molecule of interest
          weights -- the weights to use
          draw2d -- the RDKit drawing object
          colorMap -- the matplotlib color map scheme, default is custom PiWG color map
          scale -- the scaling: scale < 0 -> the absolute maximum weight is used as maximum scale
                                scale = double -> this is the maximum scale
          size -- the size of the figure
          sigma -- the sigma for the Gaussians
          coordScale -- scaling factor for the coordinates
          step -- the step for calcAtomGaussian
          colors -- color of the contour lines
          contourLines -- if integer number N: N contour lines are drawn
                          if list(numbers): contour lines at these numbers are drawn
          alpha -- the alpha blending value for the contour lines
          kwargs -- additional arguments for drawing
        
    """
def GetStandardizedWeights(weights):
    """
    
        Normalizes the weights,
        such that the absolute maximum weight equals 1.0.
    
        Parameters:
          weights -- the list with the atomic weights
        
    """
def GetTTFingerprint(mol, atomId = -1, fpType = 'normal', nBits = 2048, targetSize = 4, nBitsPerEntry = 4, **kwargs):
    """
    
        Calculates the topological torsion fingerprint with the pairs of atomId removed.
    
        Parameters:
          mol -- the molecule of interest
          atomId -- the atom to remove the torsions for (if -1, no torsion is removed)
          fpType -- the type of TT fingerprint ('normal', 'hashed', 'bv')
          nBits -- the size of the bit vector (only for fpType='bv')
          minLength -- the minimum path length for an atom pair
          maxLength -- the maxmimum path length for an atom pair
          nBitsPerEntry -- the number of bits available for each torsion
    
        any additional keyword arguments will be passed to the fingerprinting function.
    
        
    """
def _DeleteFpInfoAttr(mol):
    ...
apDict: dict  # value = {'normal': <function <lambda> at 0x7fe63621a980>, 'hashed': <function <lambda> at 0x7fe63621aa20>, 'bv': <function <lambda> at 0x7fe63621aac0>}
cm = None
ttDict: dict  # value = {'normal': <function <lambda> at 0x7fe63621ac00>, 'hashed': <function <lambda> at 0x7fe63621aca0>, 'bv': <function <lambda> at 0x7fe63621ad40>}
