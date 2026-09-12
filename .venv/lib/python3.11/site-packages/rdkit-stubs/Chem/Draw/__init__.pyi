from __future__ import annotations
from _io import BytesIO
from collections import namedtuple
from importlib.util import find_spec
import numpy as numpy
import os as os
from rdkit import Chem
from rdkit.Chem.Draw.rdMolDraw2D import ContourParams
from rdkit.Chem.Draw.rdMolDraw2D import IntStringMap
from rdkit.Chem.Draw.rdMolDraw2D import MolDraw2D
from rdkit.Chem.Draw.rdMolDraw2D import MolDraw2DCairo
from rdkit.Chem.Draw.rdMolDraw2D import MolDraw2DSVG
from rdkit.Chem.Draw.rdMolDraw2D import MolDrawOptions
from rdkit.Chem.Draw.rdMolDraw2D import MultiColourHighlightStyle
from rdkit.Chem.Draw.rdMolDraw2D import map_indexing_suite_IntStringMap_entry
from rdkit.Chem import rdDepictor
from rdkit import RDConfig
from rdkit import rdBase
import typing
import warnings as warnings
from .rdMolDraw2D import *
__all__ = ['BytesIO', 'Chem', 'CircleAndLine', 'ContourParams', 'DebugDraw', 'DrawMorganBit', 'DrawMorganBits', 'DrawMorganEnv', 'DrawMorganEnvs', 'DrawRDKitBit', 'DrawRDKitBits', 'DrawRDKitEnv', 'DrawRDKitEnvs', 'FingerprintEnv', 'IntStringMap', 'Lasso', 'MolDraw2D', 'MolDraw2DCairo', 'MolDraw2DSVG', 'MolDrawOptions', 'MolToFile', 'MolToImage', 'MolsMatrixToGridImage', 'MolsToGridImage', 'MolsToImage', 'MultiColourHighlightStyle', 'RDConfig', 'ReactionToImage', 'SetComicMode', 'ShowMol', 'calcAtomGaussians', 'find_spec', 'map_indexing_suite_IntStringMap_entry', 'namedtuple', 'numpy', 'os', 'rdBase', 'rdDepictor', 'rdMolDraw2D', 'shouldKekulize', 'warnings']
class FingerprintEnv(tuple):
    """
    FingerprintEnv(submol, highlightAtoms, atomColors, highlightBonds, bondColors, highlightRadii)
    """
    __match_args__: typing.ClassVar[tuple] = ('submol', 'highlightAtoms', 'atomColors', 'highlightBonds', 'bondColors', 'highlightRadii')
    __slots__: typing.ClassVar[tuple] = tuple()
    _field_defaults: typing.ClassVar[dict] = {}
    _fields: typing.ClassVar[tuple] = ('submol', 'highlightAtoms', 'atomColors', 'highlightBonds', 'bondColors', 'highlightRadii')
    @staticmethod
    def __new__(_cls, submol, highlightAtoms, atomColors, highlightBonds, bondColors, highlightRadii):
        """
        Create new instance of FingerprintEnv(submol, highlightAtoms, atomColors, highlightBonds, bondColors, highlightRadii)
        """
    @classmethod
    def _make(cls, iterable):
        """
        Make a new FingerprintEnv object from a sequence or iterable
        """
    def __getnewargs__(self):
        """
        Return self as a plain tuple.  Used by copy and pickle.
        """
    def __repr__(self):
        """
        Return a nicely formatted representation string
        """
    def _asdict(self):
        """
        Return a new dict which maps field names to their values.
        """
    def _replace(self, **kwds):
        """
        Return a new FingerprintEnv object replacing specified fields with new values
        """
def DebugDraw(mol, size = (350, 350), drawer = None, asSVG = True, useBW = True, includeHLabels = True, addAtomIndices = True, addBondIndices = False):
    ...
def DrawMorganBit(mol, bitId, bitInfo, whichExample = 0, **kwargs):
    ...
def DrawMorganBits(tpls, **kwargs):
    ...
def DrawMorganEnv(mol, atomId, radius, molSize = (150, 150), baseRad = 0.3, useSVG = True, aromaticColor = (0.9, 0.9, 0.2), ringColor = (0.8, 0.8, 0.8), centerColor = (0.6, 0.6, 0.9), extraColor = (0.9, 0.9, 0.9), drawOptions = None, **kwargs):
    ...
def DrawMorganEnvs(envs, molsPerRow = 3, subImgSize = (150, 150), baseRad = 0.3, useSVG = True, aromaticColor = (0.9, 0.9, 0.2), ringColor = (0.8, 0.8, 0.8), centerColor = (0.6, 0.6, 0.9), extraColor = (0.9, 0.9, 0.9), legends = None, drawOptions = None, **kwargs):
    ...
def DrawRDKitBit(mol, bitId, bitInfo, whichExample = 0, **kwargs):
    ...
def DrawRDKitBits(tpls, **kwargs):
    ...
def DrawRDKitEnv(mol, bondPath, molSize = (150, 150), baseRad = 0.3, useSVG = True, aromaticColor = (0.9, 0.9, 0.2), extraColor = (0.9, 0.9, 0.9), nonAromaticColor = None, drawOptions = None, **kwargs):
    ...
def DrawRDKitEnvs(envs, molsPerRow = 3, subImgSize = (150, 150), baseRad = 0.3, useSVG = True, aromaticColor = (0.9, 0.9, 0.2), extraColor = (0.9, 0.9, 0.9), nonAromaticColor = None, legends = None, drawOptions = None, **kwargs):
    ...
def MolToFile(mol, filename, size = (300, 300), kekulize = True, wedgeBonds = True, imageType = None, fitImage = False, options = None, **kwargs):
    """
     Generates a drawing of a molecule and writes it to a file
      
    """
def MolToImage(mol, size = (300, 300), kekulize = True, wedgeBonds = True, fitImage = False, options = None, **kwargs):
    """
    Returns a PIL image containing a drawing of the molecule
    
          ARGUMENTS:
    
            - kekulize: run kekulization routine on input `mol` (default True)
    
            - size: final image size, in pixel (default (300,300))
    
            - wedgeBonds: draw wedge (stereo) bonds (default True)
    
            - highlightAtoms: list of atoms to highlight (default [])
    
            - highlightBonds: list of bonds to highlight (default [])
    
            - highlightColor: RGB color as tuple (default [1, 0, 0])
    
          NOTE:
    
                use 'matplotlib.colors.to_rgb()' to convert string and
                HTML color codes into the RGB tuple representation, eg.
    
                  from matplotlib.colors import ColorConverter
                  img = Draw.MolToImage(m, highlightAtoms=[1,2], highlightColor=ColorConverter().to_rgb('aqua'))
                  img.save("molecule.png")
    
          RETURNS:
    
            a PIL Image object
      
    """
def MolsMatrixToGridImage(molsMatrix, subImgSize = (200, 200), legendsMatrix = None, highlightAtomListsMatrix = None, highlightBondListsMatrix = None, useSVG = False, returnPNG = False, **kwargs):
    """
    Creates a mol grid image from a nested data structure (where each data substructure represents a row),
      padding rows as needed so all rows are the length of the longest row
    
          ARGUMENTS:
    
            - molsMatrix: A two-deep nested data structure of RDKit molecules to draw,
              iterable of iterables (for example list of lists) of RDKit molecules
    
            - subImgSize: The size of a cell in the drawing; passed through to MolsToGridImage (default (200, 200))
    
            - legendsMatrix: A two-deep nested data structure of strings to label molecules with,
              iterable of iterables (for example list of lists) of strings (default None)
    
            - highlightAtomListsMatrix: A three-deep nested data structure of integers of atoms to highlight,
              iterable of iterables (for example list of lists) of integers (default None)
    
            - highlightBondListsMatrix: A three-deep nested data structure of integers of bonds to highlight,
              iterable of iterables (for example list of lists) of integers (default None)
    
            - useSVG: Whether to return an SVG (if true) or PNG (if false);
              passed through to MolsToGridImage (default false)
    
            - returnPNG: Whether to return PNG data (if true) or a PIL object for a PNG image file (if false);
              has no effect if useSVG is true; passed through to MolsToGridImage (default false)
    
            - kwargs: Any other keyword arguments are passed to MolsToGridImage
    
          NOTES:
    
                To include a blank cell in the middle of a row, supply None for that entry in molsMatrix.
                You do not need to do that for empty cells at the end of a row; 
                this function will automatically pad rows so that all rows are the same length.
                
                This function is useful when each row has some meaning,
                for example the generation in a mass spectrometry fragmentation tree--refer to 
                example at https://en.wikipedia.org/wiki/Fragmentation_(mass_spectrometry).
                If you want to display a set molecules where each row does not have any specific meaning,
                use MolsToGridImage instead.
    
                This function nests data structures one additional level beyond the analogous function MolsToGridImage
                (in which the molecules and legends are non-nested lists, 
                and the highlight parameters are two-deep nested lists) 
    
          RETURNS:
    
            A grid of molecular images in one of these formats:
            
            - useSVG=False and returnPNG=False (default): A PIL object for a PNG image file
    
            - useSVG=False and returnPNG=True: PNG data
    
            - useSVG=True: An SVG string
    
          EXAMPLES:
    
            from rdkit import Chem
            from rdkit.Chem.Draw import MolsMatrixToGridImage, rdMolDraw2D
            FCl = Chem.MolFromSmiles("FCl")
            molsMatrix = [[FCl, FCl], [FCl, None, FCl]]
    
            # Minimal example: Only molsMatrix is supplied,
            # result will be a drawing containing (where each row contains molecules):
            # F-Cl    F-Cl
            # F-Cl            F-Cl
            img = MolsMatrixToGridImage(molsMatrix)
            img.save("MolsMatrixToGridImageMinimal.png")
            # img is a PIL object for a PNG image file like:
            # <PIL.PngImagePlugin.PngImageFile image mode=RGB size=600x200 at 0x1648CC390>
            # Drawing will be saved as PNG file MolsMatrixToGridImageMinimal.png
    
            # Exhaustive example: All parameters are supplied,
            # result will be a drawing containing (where each row of molecules is followed by a row of legends):
            # 1 F-Cl 0              1 F-Cl 0
            # no highlighting       bond highlighted         
            # 1 F-Cl 0                                  1 F-Cl 0
            # sodium highlighted                        chloride and bond highlighted
            legendsMatrix = [["no highlighting", "bond highlighted"], 
            ["F highlighted", "", "Cl and bond highlighted"]]
            highlightAtomListsMatrix = [[[],[]], [[0], None, [1]]]
            highlightBondListsMatrix = [[[],[0]], [[], None, [0]]]
    
            dopts = rdMolDraw2D.MolDrawOptions()
            dopts.addAtomIndices = True
    
            img_binary = MolsMatrixToGridImage(molsMatrix=molsMatrix, subImgSize=(300, 400), 
            legendsMatrix=legendsMatrix, highlightAtomListsMatrix=highlightAtomListsMatrix, 
            highlightBondListsMatrix=highlightBondListsMatrix, useSVG=False, returnPNG=True, drawOptions=dopts)
            print(img_binary[:20])
            # Prints a binary string: b'\\x89PNG\\r\\n\\x1a\\n\\x00\\x00\\x00\\rIHDR\\x00\\x00\\x03\\x84'
      
    """
def MolsToGridImage(mols, molsPerRow = 3, subImgSize = (200, 200), legends = None, highlightAtomLists = None, highlightBondLists = None, useSVG = False, returnPNG = False, **kwargs):
    ...
def MolsToImage(mols, subImgSize = (200, 200), legends = None, **kwargs):
    """
    
      
    """
def ReactionToImage(rxn, subImgSize = (200, 200), useSVG = False, drawOptions = None, returnPNG = False, **kwargs):
    ...
def SetComicMode(opts):
    ...
def ShowMol(mol, size = (300, 300), kekulize = True, wedgeBonds = True, title = 'RDKit Molecule', stayInFront = True, **kwargs):
    """
     Generates a picture of a molecule and displays it in a Tkinter window
      
    """
def _MolsNestedToLinear(molsMatrix, legendsMatrix = None, highlightAtomListsMatrix = None, highlightBondListsMatrix = None):
    """
    Converts a nested data structure (where each data substructure represents a row in mol grid image)
      to a linear one, padding rows as needed so all rows are the length of the longest row
      
    """
def _MolsToGridImage(mols, molsPerRow = 3, subImgSize = (200, 200), legends = None, highlightAtomLists = None, highlightBondLists = None, drawOptions = None, returnPNG = False, **kwargs):
    """
     returns a PIL Image of the grid
      
    """
def _MolsToGridSVG(mols, molsPerRow = 3, subImgSize = (200, 200), legends = None, highlightAtomLists = None, highlightBondLists = None, drawOptions = None, **kwargs):
    """
     returns an SVG of the grid
      
    """
def _bivariate_normal(X, Y, sigmax = 1.0, sigmay = 1.0, mux = 0.0, muy = 0.0, sigmaxy = 0.0):
    """
    
    
        This is the implementation from matplotlib:
        https://github.com/matplotlib/matplotlib/blob/81e8154dbba54ac1607b21b22984cabf7a6598fa/lib/matplotlib/mlab.py#L1866
        it was deprecated in v2.2 of matplotlib, so we are including it here.
    
    
        Bivariate Gaussian distribution for equal shape *X*, *Y*.
        See `bivariate normal
        <http://mathworld.wolfram.com/BivariateNormalDistribution.html>`_
        at mathworld.
        
    """
def _drawerToImage(d2d):
    ...
def _flattenTwoDList(twoDList):
    ...
def _getMorganEnv(mol, atomId, radius, baseRad, aromaticColor, ringColor, centerColor, extraColor, **kwargs):
    ...
def _getRDKitEnv(mol, bondPath, baseRad, aromaticColor, extraColor, nonAromaticColor, **kwargs):
    ...
def _moltoSVG(mol, sz, highlights, legend, kekulize, drawOptions = None, **kwargs):
    ...
def _moltoimg(mol, sz, highlights, legend, returnPNG = False, drawOptions = None, **kwargs):
    ...
def _padList(inputList, lengthShouldBe, padWith = ''):
    ...
def _padMatrix(inputMatrix, rowLength, padWith = ''):
    ...
def _sip_available():
    ...
def calcAtomGaussians(mol, a = 0.03, step = 0.02, weights = None):
    """
    
      
    """
def shouldKekulize(mol, kekulize):
    ...
CircleAndLine: rdMolDraw2D.MultiColourHighlightStyle  # value = rdkit.Chem.Draw.rdMolDraw2D.MultiColourHighlightStyle.CircleAndLine
Lasso: rdMolDraw2D.MultiColourHighlightStyle  # value = rdkit.Chem.Draw.rdMolDraw2D.MultiColourHighlightStyle.Lasso
