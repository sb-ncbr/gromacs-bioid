from __future__ import annotations
import copy as copy
import functools as functools
import math as math
import numpy as numpy
from rdkit import Chem
import rdkit.Chem.rdchem
import typing
__all__ = ['Chem', 'DrawingOptions', 'Font', 'MolDrawing', 'cmp', 'copy', 'functools', 'math', 'numpy', 'periodicTable']
class DrawingOptions:
    atomLabelDeuteriumTritium: typing.ClassVar[bool] = False
    atomLabelFontFace: typing.ClassVar[str] = 'sans'
    atomLabelFontSize: typing.ClassVar[int] = 12
    atomLabelMinFontSize: typing.ClassVar[int] = 7
    atomNumberOffset: typing.ClassVar[int] = 0
    bgColor: typing.ClassVar[tuple] = (1, 1, 1)
    bondLineWidth: typing.ClassVar[float] = 1.2
    colorBonds: typing.ClassVar[bool] = True
    coordScale: typing.ClassVar[float] = 1.0
    dash: typing.ClassVar[tuple] = (4, 4)
    dblBondLengthFrac: typing.ClassVar[float] = 0.8
    dblBondOffset: typing.ClassVar[float] = 0.25
    defaultColor: typing.ClassVar[tuple] = (1, 0, 0)
    dotsPerAngstrom: typing.ClassVar[int] = 30
    elemDict: typing.ClassVar[dict] = {1: (0.55, 0.55, 0.55), 7: (0, 0, 1), 8: (1, 0, 0), 9: (0.2, 0.8, 0.8), 15: (1, 0.5, 0), 16: (0.8, 0.8, 0), 17: (0, 0.8, 0), 35: (0.5, 0.3, 0.1), 53: (0.63, 0.12, 0.94), 0: (0.5, 0.5, 0.5)}
    includeAtomNumbers: typing.ClassVar[bool] = False
    noCarbonSymbols: typing.ClassVar[bool] = True
    radicalSymbol: typing.ClassVar[str] = '∙'
    selectColor: typing.ClassVar[tuple] = (1, 0, 0)
    showUnknownDoubleBonds: typing.ClassVar[bool] = True
    useFraction: typing.ClassVar[float] = 0.85
    wedgeDashedBonds: typing.ClassVar[bool] = True
class Font:
    def __init__(self, face = None, size = None, name = None, weight = None):
        ...
class MolDrawing:
    def AddMol(self, mol, centerIt = True, molTrans = None, drawingTrans = None, highlightAtoms = list(), confId = -1, flagCloseContactsDist = 2, highlightMap = None, ignoreHs = False, highlightBonds = list(), **kwargs):
        """
        Set the molecule to be drawn.
        
            Parameters:
              hightlightAtoms -- list of atoms to highlight (default [])
              highlightMap -- dictionary of (atom, color) pairs (default None)
        
            Notes:
              - specifying centerIt will cause molTrans and drawingTrans to be ignored
            
        """
    def __init__(self, canvas = None, drawingOptions = None):
        ...
    def _drawBond(self, bond, atom, nbr, pos, nbrPos, conf, width = None, color = None, color2 = None, labelSize1 = None, labelSize2 = None):
        ...
    def _drawLabel(self, label, pos, baseOffset, font, color = None, **kwargs):
        ...
    def _drawWedgedBond(self, bond, pos, nbrPos, width = None, color = None, dash = None):
        ...
    def _getBondAttachmentCoordinates(self, p1, p2, labelSize):
        ...
    def _getBondOffset(self, p1, p2):
        ...
    def _getOffsetBondPts(self, p1, p2, offsetX, offsetY, lenFrac = None):
        ...
    def _offsetDblBond(self, p1, p2, bond, a1, a2, conf, direction = 1, lenFrac = None):
        ...
    def scaleAndCenter(self, mol, conf, coordCenter = False, canvasSize = None, ignoreHs = False):
        ...
    def transformPoint(self, pos):
        ...
def cmp(t1, t2):
    ...
periodicTable: rdkit.Chem.rdchem.PeriodicTable  # value = <rdkit.Chem.rdchem.PeriodicTable object>
