"""
Module containing a C++ implementation of 2D molecule drawing
"""
from __future__ import annotations
import rdkit.Chem
import typing
__all__ = ['CircleAndLine', 'ContourAndDrawGaussians', 'ContourAndDrawGrid', 'ContourParams', 'DrawMoleculeACS1996', 'IntStringMap', 'Lasso', 'MeanBondLength', 'MolDraw2D', 'MolDraw2DCairo', 'MolDraw2DSVG', 'MolDrawOptions', 'MolToACS1996SVG', 'MolToSVG', 'MultiColourHighlightStyle', 'PrepareAndDrawMolecule', 'PrepareMolForDrawing', 'SetACS1996Mode', 'SetDarkMode', 'SetMonochromeMode', 'UpdateDrawerParamsFromJSON', 'UpdateMolDrawOptionsFromJSON', 'map_indexing_suite_IntStringMap_entry']
class ContourParams(Boost.Python.instance):
    """
    Parameters for drawing contours
    """
    __instance_size__: typing.ClassVar[int] = 136
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    def setColourMap(self, colours: typing.Any) -> None:
        """
            C++ signature :
                void setColourMap(RDKit::MolDraw2DUtils::ContourParams {lvalue},boost::python::api::object)
        """
    def setContourColour(self, colour: tuple) -> None:
        """
            C++ signature :
                void setContourColour(RDKit::MolDraw2DUtils::ContourParams {lvalue},boost::python::tuple)
        """
    @property
    def contourWidth(*args, **kwargs):
        """
        line width of the contours
        """
    @contourWidth.setter
    def contourWidth(*args, **kwargs):
        ...
    @property
    def coordScaleForQuantization(*args, **kwargs):
        """
        scaling factor used to convert coordinates to ints when forming the continuous lines
        """
    @coordScaleForQuantization.setter
    def coordScaleForQuantization(*args, **kwargs):
        ...
    @property
    def dashNegative(*args, **kwargs):
        """
        use a dashed line for negative contours
        """
    @dashNegative.setter
    def dashNegative(*args, **kwargs):
        ...
    @property
    def drawAsLines(*args, **kwargs):
        """
        draw the contours as continuous lines isntead of line segments
        """
    @drawAsLines.setter
    def drawAsLines(*args, **kwargs):
        ...
    @property
    def extraGridPadding(*args, **kwargs):
        """
        extra space (in molecule coords) around the grid
        """
    @extraGridPadding.setter
    def extraGridPadding(*args, **kwargs):
        ...
    @property
    def fillGrid(*args, **kwargs):
        """
        colors the grid in addition to drawing contours
        """
    @fillGrid.setter
    def fillGrid(*args, **kwargs):
        ...
    @property
    def gridResolution(*args, **kwargs):
        """
        set the resolution of the grid
        """
    @gridResolution.setter
    def gridResolution(*args, **kwargs):
        ...
    @property
    def isovalScaleForQuantization(*args, **kwargs):
        """
        scaling factor used to convert isovalues to ints when forming the continuous lines
        """
    @isovalScaleForQuantization.setter
    def isovalScaleForQuantization(*args, **kwargs):
        ...
    @property
    def setScale(*args, **kwargs):
        """
        set the scale of the drawing object (useful if you draw the grid/contours first)
        """
    @setScale.setter
    def setScale(*args, **kwargs):
        ...
class IntStringMap(Boost.Python.instance):
    __instance_size__: typing.ClassVar[int] = 72
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __contains__(self, item: typing.Any) -> bool:
        """
            C++ signature :
                bool __contains__(std::map<int, std::string, std::less<int>, std::allocator<std::pair<int const, std::string> > > {lvalue},_object*)
        """
    def __delitem__(self, item: typing.Any) -> None:
        """
            C++ signature :
                void __delitem__(std::map<int, std::string, std::less<int>, std::allocator<std::pair<int const, std::string> > > {lvalue},_object*)
        """
    def __getitem__(self, item: typing.Any) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object __getitem__(boost::python::back_reference<std::map<int, std::string, std::less<int>, std::allocator<std::pair<int const, std::string> > >&>,_object*)
        """
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    def __iter__(self) -> typing.Any:
        """
            C++ signature :
                boost::python::objects::iterator_range<boost::python::return_value_policy<boost::python::return_by_value, boost::python::default_call_policies>, std::_Rb_tree_iterator<std::pair<int const, std::string> > > __iter__(boost::python::back_reference<std::map<int, std::string, std::less<int>, std::allocator<std::pair<int const, std::string> > >&>)
        """
    def __len__(self) -> int:
        """
            C++ signature :
                unsigned long __len__(std::map<int, std::string, std::less<int>, std::allocator<std::pair<int const, std::string> > > {lvalue})
        """
    def __setitem__(self, item: typing.Any, value: typing.Any) -> None:
        """
            C++ signature :
                void __setitem__(std::map<int, std::string, std::less<int>, std::allocator<std::pair<int const, std::string> > > {lvalue},_object*,_object*)
        """
class MolDraw2D(Boost.Python.instance):
    """
    Drawer abstract base class
    """
    @staticmethod
    def __init__(*args, **kwargs):
        """
        Raises an exception
        This class cannot be instantiated from Python
        """
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def ClearDrawing(self) -> None:
        """
            clears the drawing by filling it with the background color
        
            C++ signature :
                void ClearDrawing(RDKit::MolDraw2D {lvalue})
        """
    def DrawArc(self, center: Point2D, radius: float, angle1: float, angle2: float, rawCoords: bool = False) -> None:
        """
            draws an arc with the current drawing style. The coordinates are in the molecule frame, the angles are in degrees, angle2 should be > angle1.
        
            C++ signature :
                void DrawArc(RDKit::MolDraw2D {lvalue},RDGeom::Point2D,double,double,double [,bool=False])
        """
    def DrawArrow(self, cds1: Point2D, cds2: Point2D, asPolygon: bool = False, frac: float = 0.05, angle: float = 0.5235987755982988, color: typing.Any = None, rawCoords: bool = False) -> None:
        """
            draws an arrow with the current drawing style. The coordinates are in the molecule frame. If asPolygon is true the head of the arrow will be drawn as a triangle, otherwise two lines are used.
        
            C++ signature :
                void DrawArrow(RDKit::MolDraw2D {lvalue},RDGeom::Point2D,RDGeom::Point2D [,bool=False [,double=0.05 [,double=0.5235987755982988 [,boost::python::api::object=None [,bool=False]]]]])
        """
    def DrawAttachmentLine(self, cds1: Point2D, cds2: Point2D, color: tuple, len: float = 1.0, nSegments: int = 16, rawCoords: bool = False) -> None:
        """
            draw a line indicating the presence of an attachment point (normally a squiggle line perpendicular to a bond)
        
            C++ signature :
                void DrawAttachmentLine(RDKit::MolDraw2D {lvalue},RDGeom::Point2D,RDGeom::Point2D,boost::python::tuple {lvalue} [,double=1.0 [,unsigned int=16 [,bool=False]]])
        """
    def DrawEllipse(self, cds1: Point2D, cds2: Point2D, rawCoords: bool = False) -> None:
        """
            draws a triangle with the current drawing style in the rectangle defined by the two points. The coordinates are in the molecule frame
        
            C++ signature :
                void DrawEllipse(RDKit::MolDraw2D {lvalue},RDGeom::Point2D,RDGeom::Point2D [,bool=False])
        """
    def DrawLine(self, cds1: Point2D, cds2: Point2D, rawCoords: bool = False) -> None:
        """
            draws a line with the current drawing style. The coordinates are in the molecule frame
        
            C++ signature :
                void DrawLine(RDKit::MolDraw2D {lvalue},RDGeom::Point2D,RDGeom::Point2D [,bool=False])
        """
    @typing.overload
    def DrawMolecule(self, mol: Mol, highlightAtoms: typing.Any = None, highlightAtomColors: typing.Any = None, highlightAtomRadii: typing.Any = None, confId: int = -1, legend: str = '') -> None:
        """
            renders a molecule
            
        
            C++ signature :
                void DrawMolecule(RDKit::MolDraw2D {lvalue},RDKit::ROMol [,boost::python::api::object=None [,boost::python::api::object=None [,boost::python::api::object=None [,int=-1 [,std::string='']]]]])
        """
    @typing.overload
    def DrawMolecule(self, mol: Mol, highlightAtoms: typing.Any, highlightBonds: typing.Any, highlightAtomColors: typing.Any = None, highlightBondColors: typing.Any = None, highlightAtomRadii: typing.Any = None, confId: int = -1, legend: str = '') -> None:
        """
            renders a molecule
            
        
            C++ signature :
                void DrawMolecule(RDKit::MolDraw2D {lvalue},RDKit::ROMol,boost::python::api::object,boost::python::api::object [,boost::python::api::object=None [,boost::python::api::object=None [,boost::python::api::object=None [,int=-1 [,std::string='']]]]])
        """
    def DrawMoleculeWithHighlights(self, mol: Mol, legend: str, highlight_atom_map: typing.Any, highlight_bond_map: typing.Any, highlight_radii: typing.Any, highlight_linewidth_multipliers: typing.Any, confId: int = -1) -> None:
        """
            renders a molecule with multiple highlight colours
            
        
            C++ signature :
                void DrawMoleculeWithHighlights(RDKit::MolDraw2D {lvalue},RDKit::ROMol,std::string,boost::python::api::object,boost::python::api::object,boost::python::api::object,boost::python::api::object [,int=-1])
        """
    def DrawMolecules(self, mols: typing.Any, highlightAtoms: typing.Any = None, highlightBonds: typing.Any = None, highlightAtomColors: typing.Any = None, highlightBondColors: typing.Any = None, highlightAtomRadii: typing.Any = None, confIds: typing.Any = None, legends: typing.Any = None) -> None:
        """
            renders multiple molecules
            
        
            C++ signature :
                void DrawMolecules(RDKit::MolDraw2D {lvalue},boost::python::api::object [,boost::python::api::object=None [,boost::python::api::object=None [,boost::python::api::object=None [,boost::python::api::object=None [,boost::python::api::object=None [,boost::python::api::object=None [,boost::python::api::object=None]]]]]]])
        """
    def DrawPolygon(self, cds: typing.Any, rawCoords: bool = False) -> None:
        """
            draws a polygon with the current drawing style. The coordinates are in the molecule frame
        
            C++ signature :
                void DrawPolygon(RDKit::MolDraw2D {lvalue},boost::python::api::object [,bool=False])
        """
    def DrawReaction(self, rxn: typing.Any, highlightByReactant: bool = False, highlightColorsReactants: typing.Any = None, confIds: typing.Any = None) -> None:
        """
            renders a reaction
            
        
            C++ signature :
                void DrawReaction(RDKit::MolDraw2D {lvalue},RDKit::ChemicalReaction [,bool=False [,boost::python::api::object=None [,boost::python::api::object=None]]])
        """
    def DrawRect(self, cds1: Point2D, cds2: Point2D, rawCoords: bool = False) -> None:
        """
            draws a rectangle with the current drawing style in the rectangle defined by the two points. The coordinates are in the molecule frame
        
            C++ signature :
                void DrawRect(RDKit::MolDraw2D {lvalue},RDGeom::Point2D,RDGeom::Point2D [,bool=False])
        """
    @typing.overload
    def DrawString(self, string: str, pos: Point2D, rawCoords: bool = False) -> None:
        """
            add text to the canvas
        
            C++ signature :
                void DrawString(RDKit::MolDraw2D {lvalue},std::string,RDGeom::Point2D [,bool=False])
        """
    @typing.overload
    def DrawString(self, string: str, pos: Point2D, align: int, rawCoords: bool = False) -> None:
        """
            add aligned text to the canvas. The align argument can be 0 (=MIDDLE), 1 (=START), or 2 (=END)
        
            C++ signature :
                void DrawString(RDKit::MolDraw2D {lvalue},std::string,RDGeom::Point2D,int [,bool=False])
        """
    def DrawTriangle(self, cds1: Point2D, cds2: Point2D, cds3: Point2D, rawCoords: bool = False) -> None:
        """
            draws a triangle with the current drawing style. The coordinates are in the molecule frame
        
            C++ signature :
                void DrawTriangle(RDKit::MolDraw2D {lvalue},RDGeom::Point2D,RDGeom::Point2D,RDGeom::Point2D [,bool=False])
        """
    def DrawWavyLine(self, cds1: Point2D, cds2: Point2D, color1: tuple, color2: tuple, nSegments: int = 16, vertOffset: float = 0.05, rawCoords: bool = False) -> None:
        """
            draw a line indicating the presence of an attachment point (normally a squiggle line perpendicular to a bond)
        
            C++ signature :
                void DrawWavyLine(RDKit::MolDraw2D {lvalue},RDGeom::Point2D,RDGeom::Point2D,boost::python::tuple {lvalue},boost::python::tuple {lvalue} [,unsigned int=16 [,double=0.05 [,bool=False]]])
        """
    def FillPolys(self) -> bool:
        """
            returns whether or not polygons are being filled
        
            C++ signature :
                bool FillPolys(RDKit::MolDraw2D {lvalue})
        """
    def FlexiMode(self) -> bool:
        """
            returns whether or not FlexiMode is being used
        
            C++ signature :
                bool FlexiMode(RDKit::MolDraw2D {lvalue})
        """
    def FontSize(self) -> float:
        """
            get the default font size. The units are, roughly, pixels.
        
            C++ signature :
                double FontSize(RDKit::MolDraw2D {lvalue})
        """
    @typing.overload
    def GetDrawCoords(self, point: Point2D) -> Point2D:
        """
            get the coordinates in drawing space for a particular point in molecule space
        
            C++ signature :
                RDGeom::Point2D GetDrawCoords(RDKit::MolDraw2D {lvalue},RDGeom::Point2D)
        """
    @typing.overload
    def GetDrawCoords(self, atomIndex: int) -> Point2D:
        """
            get the coordinates in drawing space for a particular atom
        
            C++ signature :
                RDGeom::Point2D GetDrawCoords(RDKit::MolDraw2D {lvalue},int)
        """
    def GetMolSize(self, mol: Mol, highlightAtoms: typing.Any = None, highlightBonds: typing.Any = None, highlightAtomColors: typing.Any = None, highlightBondColors: typing.Any = None, highlightAtomRadii: typing.Any = None, confId: int = -1, legend: str = '') -> tuple:
        """
            returns the width and height required to draw a molecule at the current size
        
            C++ signature :
                boost::python::tuple GetMolSize(RDKit::MolDraw2D {lvalue},RDKit::ROMol [,boost::python::api::object=None [,boost::python::api::object=None [,boost::python::api::object=None [,boost::python::api::object=None [,boost::python::api::object=None [,int=-1 [,std::string='']]]]]]])
        """
    def Height(self) -> int:
        """
            get the height of the drawing canvas
        
            C++ signature :
                int Height(RDKit::MolDraw2D {lvalue})
        """
    def LineWidth(self) -> float:
        """
            returns the line width being used
        
            C++ signature :
                double LineWidth(RDKit::MolDraw2D {lvalue})
        """
    def Offset(self) -> Point2D:
        """
            returns the offset (in drawing coordinates) for the drawing
        
            C++ signature :
                RDGeom::Point2D Offset(RDKit::MolDraw2D {lvalue})
        """
    def SetColour(self, tpl: tuple) -> None:
        """
            set the color being used fr drawing and filling
        
            C++ signature :
                void SetColour(RDKit::MolDraw2D {lvalue},boost::python::tuple)
        """
    def SetDrawOptions(self, opts: MolDrawOptions) -> None:
        """
            Copies the drawing options passed in over our drawing options
        
            C++ signature :
                void SetDrawOptions(RDKit::MolDraw2D {lvalue},RDKit::MolDrawOptions)
        """
    def SetFillPolys(self, val: bool) -> None:
        """
            sets whether or not polygons are filled
        
            C++ signature :
                void SetFillPolys(RDKit::MolDraw2D {lvalue},bool)
        """
    def SetFlexiMode(self, mode: bool) -> None:
        """
            when FlexiMode is set, molecules will always been drawn with the default values for bond length, font size, etc.
        
            C++ signature :
                void SetFlexiMode(RDKit::MolDraw2D {lvalue},bool)
        """
    def SetFontSize(self, new_size: float) -> None:
        """
            change the default font size. The units are, roughly, pixels.
        
            C++ signature :
                void SetFontSize(RDKit::MolDraw2D {lvalue},double)
        """
    def SetLineWidth(self, width: float) -> None:
        """
            set the line width being used
        
            C++ signature :
                void SetLineWidth(RDKit::MolDraw2D {lvalue},double)
        """
    def SetOffset(self, x: int, y: int) -> None:
        """
            set the offset (in drawing coordinates) for the drawing
        
            C++ signature :
                void SetOffset(RDKit::MolDraw2D {lvalue},int,int)
        """
    def SetScale(self, width: int, height: int, minv: Point2D, maxv: Point2D, mol: typing.Any = None) -> None:
        """
            uses the values provided to set the drawing scaling
        
            C++ signature :
                void SetScale(RDKit::MolDraw2D {lvalue},int,int,RDGeom::Point2D,RDGeom::Point2D [,boost::python::api::object=None])
        """
    def Width(self) -> int:
        """
            get the width of the drawing canvas
        
            C++ signature :
                int Width(RDKit::MolDraw2D {lvalue})
        """
    def drawOptions(self) -> MolDrawOptions:
        """
            Returns a modifiable version of the current drawing options
        
            C++ signature :
                RDKit::MolDrawOptions {lvalue} drawOptions(RDKit::MolDraw2D {lvalue})
        """
class MolDraw2DCairo(MolDraw2D):
    """
    Cairo molecule drawer
    """
    __instance_size__: typing.ClassVar[int] = 856
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def FinishDrawing(self) -> None:
        """
            add the last bits to finish the drawing
        
            C++ signature :
                void FinishDrawing(RDKit::MolDraw2DCairo {lvalue})
        """
    def GetDrawingText(self) -> typing.Any:
        """
            return the PNG data as a string
        
            C++ signature :
                boost::python::api::object GetDrawingText(RDKit::MolDraw2DCairo)
        """
    def WriteDrawingText(self, fName: str) -> None:
        """
            write the PNG data to the named file
        
            C++ signature :
                void WriteDrawingText(RDKit::MolDraw2DCairo {lvalue},std::string)
        """
    def __init__(self, width: int, height: int, panelWidth: int = -1, panelHeight: int = -1, noFreetype: bool = False) -> None:
        """
            C++ signature :
                void __init__(_object*,int,int [,int=-1 [,int=-1 [,bool=False]]])
        """
class MolDraw2DSVG(MolDraw2D):
    """
    SVG molecule drawer
    """
    __instance_size__: typing.ClassVar[int] = 1216
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def AddMoleculeMetadata(self, mol: Mol, confId: int = -1) -> None:
        """
            add RDKit-specific information to the bottom of the drawing
        
            C++ signature :
                void AddMoleculeMetadata(RDKit::MolDraw2DSVG {lvalue},RDKit::ROMol [,int=-1])
        """
    def FinishDrawing(self) -> None:
        """
            add the last bits of SVG to finish the drawing
        
            C++ signature :
                void FinishDrawing(RDKit::MolDraw2DSVG {lvalue})
        """
    def GetDrawingText(self) -> str:
        """
            return the SVG
        
            C++ signature :
                std::string GetDrawingText(RDKit::MolDraw2DSVG {lvalue})
        """
    def TagAtoms(self, mol: Mol, radius: float = 0.2, events: typing.Any = None) -> None:
        """
            allow atom selection in the SVG
        
            C++ signature :
                void TagAtoms(RDKit::MolDraw2DSVG {lvalue},RDKit::ROMol [,double=0.2 [,boost::python::api::object=None]])
        """
    def __init__(self, width: int, height: int, panelWidth: int = -1, panelHeight: int = -1, noFreetype: bool = False) -> None:
        """
            C++ signature :
                void __init__(_object*,int,int [,int=-1 [,int=-1 [,bool=False]]])
        """
class MolDrawOptions(Boost.Python.instance):
    """
    Drawing options
    """
    __instance_size__: typing.ClassVar[int] = 616
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    def getAnnotationColour(self) -> typing.Any:
        """
            method returning the annotation colour
        
            C++ signature :
                boost::python::api::object getAnnotationColour(RDKit::MolDrawOptions)
        """
    def getBackgroundColour(self) -> typing.Any:
        """
            method returning the background colour
        
            C++ signature :
                boost::python::api::object getBackgroundColour(RDKit::MolDrawOptions)
        """
    def getHighlightColour(self) -> typing.Any:
        """
            method returning the highlight colour
        
            C++ signature :
                boost::python::api::object getHighlightColour(RDKit::MolDrawOptions)
        """
    def getLegendColour(self) -> typing.Any:
        """
            method returning the legend colour
        
            C++ signature :
                boost::python::api::object getLegendColour(RDKit::MolDrawOptions)
        """
    def getQueryColour(self) -> typing.Any:
        """
            method returning the query colour
        
            C++ signature :
                boost::python::api::object getQueryColour(RDKit::MolDrawOptions)
        """
    def getSymbolColour(self) -> typing.Any:
        """
            method returning the symbol colour
        
            C++ signature :
                boost::python::api::object getSymbolColour(RDKit::MolDrawOptions)
        """
    def getVariableAttachmentColour(self) -> typing.Any:
        """
            method for getting the colour of variable attachment points
        
            C++ signature :
                boost::python::api::object getVariableAttachmentColour(RDKit::MolDrawOptions)
        """
    def setAnnotationColour(self, tpl: tuple) -> None:
        """
            method for setting the annotation colour
        
            C++ signature :
                void setAnnotationColour(RDKit::MolDrawOptions {lvalue},boost::python::tuple)
        """
    def setAtomPalette(self, cmap: typing.Any) -> None:
        """
            sets the palette for atoms and bonds from a dictionary mapping ints to 3-tuples
        
            C++ signature :
                void setAtomPalette(RDKit::MolDrawOptions {lvalue},boost::python::api::object)
        """
    def setBackgroundColour(self, tpl: tuple) -> None:
        """
            method for setting the background colour
        
            C++ signature :
                void setBackgroundColour(RDKit::MolDrawOptions {lvalue},boost::python::tuple)
        """
    def setHighlightColour(self, tpl: tuple) -> None:
        """
            method for setting the highlight colour
        
            C++ signature :
                void setHighlightColour(RDKit::MolDrawOptions {lvalue},boost::python::tuple)
        """
    def setLegendColour(self, tpl: tuple) -> None:
        """
            method for setting the legend colour
        
            C++ signature :
                void setLegendColour(RDKit::MolDrawOptions {lvalue},boost::python::tuple)
        """
    def setQueryColour(self, tpl: tuple) -> None:
        """
            method for setting the query colour
        
            C++ signature :
                void setQueryColour(RDKit::MolDrawOptions {lvalue},boost::python::tuple)
        """
    def setSymbolColour(self, tpl: tuple) -> None:
        """
            method for setting the symbol colour
        
            C++ signature :
                void setSymbolColour(RDKit::MolDrawOptions {lvalue},boost::python::tuple)
        """
    def setVariableAttachmentColour(self, tpl: tuple) -> None:
        """
            method for setting the colour of variable attachment points
        
            C++ signature :
                void setVariableAttachmentColour(RDKit::MolDrawOptions {lvalue},boost::python::tuple)
        """
    def updateAtomPalette(self, cmap: typing.Any) -> None:
        """
            updates the palette for atoms and bonds from a dictionary mapping ints to 3-tuples
        
            C++ signature :
                void updateAtomPalette(RDKit::MolDrawOptions {lvalue},boost::python::api::object)
        """
    def useAvalonAtomPalette(self) -> None:
        """
            use the Avalon renderer palette for atoms and bonds
        
            C++ signature :
                void useAvalonAtomPalette(RDKit::MolDrawOptions {lvalue})
        """
    def useBWAtomPalette(self) -> None:
        """
            use a black and white palette for atoms and bonds
        
            C++ signature :
                void useBWAtomPalette(RDKit::MolDrawOptions {lvalue})
        """
    def useCDKAtomPalette(self) -> None:
        """
            use the CDK palette for atoms and bonds
        
            C++ signature :
                void useCDKAtomPalette(RDKit::MolDrawOptions {lvalue})
        """
    def useDefaultAtomPalette(self) -> None:
        """
            use the default colour palette for atoms and bonds
        
            C++ signature :
                void useDefaultAtomPalette(RDKit::MolDrawOptions {lvalue})
        """
    @property
    def addAtomIndices(*args, **kwargs):
        """
        adds atom indices to drawings. Default False.
        """
    @addAtomIndices.setter
    def addAtomIndices(*args, **kwargs):
        ...
    @property
    def addBondIndices(*args, **kwargs):
        """
        adds bond indices to drawings. Default False.
        """
    @addBondIndices.setter
    def addBondIndices(*args, **kwargs):
        ...
    @property
    def addStereoAnnotation(*args, **kwargs):
        """
        adds R/S and E/Z to drawings. Default False.
        """
    @addStereoAnnotation.setter
    def addStereoAnnotation(*args, **kwargs):
        ...
    @property
    def additionalAtomLabelPadding(*args, **kwargs):
        """
        additional padding to leave around atom labels. Expressed as a fraction of the font size.
        """
    @additionalAtomLabelPadding.setter
    def additionalAtomLabelPadding(*args, **kwargs):
        ...
    @property
    def annotationFontScale(*args, **kwargs):
        """
        Scale of font for atom and bond annotation relative to atomlabel font.  Default=0.75.
        """
    @annotationFontScale.setter
    def annotationFontScale(*args, **kwargs):
        ...
    @property
    def atomHighlightsAreCircles(*args, **kwargs):
        """
        forces atom highlights always to be circles.Default (false) is to put ellipses roundlonger labels.
        """
    @atomHighlightsAreCircles.setter
    def atomHighlightsAreCircles(*args, **kwargs):
        ...
    @property
    def atomLabelDeuteriumTritium(*args, **kwargs):
        """
        labels deuterium as D and tritium as T
        """
    @atomLabelDeuteriumTritium.setter
    def atomLabelDeuteriumTritium(*args, **kwargs):
        ...
    @property
    def atomLabels(*args, **kwargs):
        """
        maps indices to atom labels
        """
    @atomLabels.setter
    def atomLabels(*args, **kwargs):
        ...
    @property
    def atomRegions(*args, **kwargs):
        """
        regions to outline
        """
    @atomRegions.setter
    def atomRegions(*args, **kwargs):
        ...
    @property
    def baseFontSize(*args, **kwargs):
        """
        relative size of font.  Defaults to 0.6.  -1 means use default.
        """
    @baseFontSize.setter
    def baseFontSize(*args, **kwargs):
        ...
    @property
    def bondLineWidth(*args, **kwargs):
        """
        if positive, this overrides the default line width for bonds
        """
    @bondLineWidth.setter
    def bondLineWidth(*args, **kwargs):
        ...
    @property
    def bracketsAroundAtomLists(*args, **kwargs):
        """
        Whether to put brackets round atom lists in query atoms.  Default is true.
        """
    @bracketsAroundAtomLists.setter
    def bracketsAroundAtomLists(*args, **kwargs):
        ...
    @property
    def centreMoleculesBeforeDrawing(*args, **kwargs):
        """
        Moves the centre of the drawn molecule to (0,0).Default False.
        """
    @centreMoleculesBeforeDrawing.setter
    def centreMoleculesBeforeDrawing(*args, **kwargs):
        ...
    @property
    def circleAtoms(*args, **kwargs):
        ...
    @circleAtoms.setter
    def circleAtoms(*args, **kwargs):
        ...
    @property
    def clearBackground(*args, **kwargs):
        """
        clear the background before drawing a molecule
        """
    @clearBackground.setter
    def clearBackground(*args, **kwargs):
        ...
    @property
    def comicMode(*args, **kwargs):
        """
        simulate hand-drawn lines for bonds. When combined with a font like Comic-Sans or Comic-Neue, this gives xkcd-like drawings. Default is false.
        """
    @comicMode.setter
    def comicMode(*args, **kwargs):
        ...
    @property
    def continuousHighlight(*args, **kwargs):
        ...
    @continuousHighlight.setter
    def continuousHighlight(*args, **kwargs):
        ...
    @property
    def drawMolsSameScale(*args, **kwargs):
        """
        when drawing multiple molecules with DrawMolecules, forces them to use the same scale.  Default is true.
        """
    @drawMolsSameScale.setter
    def drawMolsSameScale(*args, **kwargs):
        ...
    @property
    def dummiesAreAttachments(*args, **kwargs):
        ...
    @dummiesAreAttachments.setter
    def dummiesAreAttachments(*args, **kwargs):
        ...
    @property
    def dummyIsotopeLabels(*args, **kwargs):
        """
        adds isotope labels on dummy atoms. Default True.
        """
    @dummyIsotopeLabels.setter
    def dummyIsotopeLabels(*args, **kwargs):
        ...
    @property
    def explicitMethyl(*args, **kwargs):
        """
        Draw terminal methyls explictly.  Default is false.
        """
    @explicitMethyl.setter
    def explicitMethyl(*args, **kwargs):
        ...
    @property
    def fillHighlights(*args, **kwargs):
        ...
    @fillHighlights.setter
    def fillHighlights(*args, **kwargs):
        ...
    @property
    def fixedBondLength(*args, **kwargs):
        """
        If > 0.0, fixes bond length to this number of pixelsunless that would make it too big.  Default -1.0 meansno fix.  If both set, fixedScale takes precedence.
        """
    @fixedBondLength.setter
    def fixedBondLength(*args, **kwargs):
        ...
    @property
    def fixedFontSize(*args, **kwargs):
        """
        font size in pixels. default=-1 means not fixed.  If set, always used irrespective of scale, minFontSize and maxFontSize.
        """
    @fixedFontSize.setter
    def fixedFontSize(*args, **kwargs):
        ...
    @property
    def fixedScale(*args, **kwargs):
        """
        If > 0.0, fixes scale to that fraction of width ofdraw window.  Default -1.0 means adjust scale to fit.
        """
    @fixedScale.setter
    def fixedScale(*args, **kwargs):
        ...
    @property
    def flagCloseContactsDist(*args, **kwargs):
        ...
    @flagCloseContactsDist.setter
    def flagCloseContactsDist(*args, **kwargs):
        ...
    @property
    def fontFile(*args, **kwargs):
        """
        Font file for use with FreeType text drawer.  Can also be BuiltinTelexRegular (the default) or BuiltinRobotoRegular.
        """
    @fontFile.setter
    def fontFile(*args, **kwargs):
        ...
    @property
    def highlightBondWidthMultiplier(*args, **kwargs):
        """
        What to multiply default bond width by for highlighting bonds. Default-8.
        """
    @highlightBondWidthMultiplier.setter
    def highlightBondWidthMultiplier(*args, **kwargs):
        ...
    @property
    def highlightRadius(*args, **kwargs):
        """
        Default radius for highlight circles.
        """
    @highlightRadius.setter
    def highlightRadius(*args, **kwargs):
        ...
    @property
    def includeAtomTags(*args, **kwargs):
        """
        include atom tags in output
        """
    @includeAtomTags.setter
    def includeAtomTags(*args, **kwargs):
        ...
    @property
    def includeChiralFlagLabel(*args, **kwargs):
        """
        add a molecule annotation with "ABS" if the chiral flag is set. Default is false.
        """
    @includeChiralFlagLabel.setter
    def includeChiralFlagLabel(*args, **kwargs):
        ...
    @property
    def includeMetadata(*args, **kwargs):
        """
        When possible, include metadata about molecules and reactions to allow them to be reconstructed. Default is true.
        """
    @includeMetadata.setter
    def includeMetadata(*args, **kwargs):
        ...
    @property
    def includeRadicals(*args, **kwargs):
        """
        include radicals in the drawing (it can be useful to turn this off for reactions and queries). Default is true.
        """
    @includeRadicals.setter
    def includeRadicals(*args, **kwargs):
        ...
    @property
    def isotopeLabels(*args, **kwargs):
        """
        adds isotope labels on non-dummy atoms. Default True.
        """
    @isotopeLabels.setter
    def isotopeLabels(*args, **kwargs):
        ...
    @property
    def legendFontSize(*args, **kwargs):
        """
        font size in pixels of the legend (if drawn)
        """
    @legendFontSize.setter
    def legendFontSize(*args, **kwargs):
        ...
    @property
    def legendFraction(*args, **kwargs):
        """
        fraction of the draw panel to be used for the legend if present
        """
    @legendFraction.setter
    def legendFraction(*args, **kwargs):
        ...
    @property
    def maxFontSize(*args, **kwargs):
        """
        maximum font size in pixels. default=40, -1 means no maximum.
        """
    @maxFontSize.setter
    def maxFontSize(*args, **kwargs):
        ...
    @property
    def minFontSize(*args, **kwargs):
        """
        minimum font size in pixels. default=6, -1 means no minimum.
        """
    @minFontSize.setter
    def minFontSize(*args, **kwargs):
        ...
    @property
    def multiColourHighlightStyle(*args, **kwargs):
        """
        Either 'CircleAndLine' or 'Lasso', to control style ofmulti-coloured highlighting in DrawMoleculeWithHighlights.Default is CircleAndLine.
        """
    @multiColourHighlightStyle.setter
    def multiColourHighlightStyle(*args, **kwargs):
        ...
    @property
    def multipleBondOffset(*args, **kwargs):
        """
        offset for the extra lines in a multiple bond as a fraction of mean bond length
        """
    @multipleBondOffset.setter
    def multipleBondOffset(*args, **kwargs):
        ...
    @property
    def noAtomLabels(*args, **kwargs):
        """
        disables inclusion of atom labels in the rendering
        """
    @noAtomLabels.setter
    def noAtomLabels(*args, **kwargs):
        ...
    @property
    def padding(*args, **kwargs):
        """
        fraction of empty space to leave around molecule
        """
    @padding.setter
    def padding(*args, **kwargs):
        ...
    @property
    def prepareMolsBeforeDrawing(*args, **kwargs):
        """
        call prepareMolForDrawing() on each molecule passed to DrawMolecules()
        """
    @prepareMolsBeforeDrawing.setter
    def prepareMolsBeforeDrawing(*args, **kwargs):
        ...
    @property
    def rotate(*args, **kwargs):
        """
        Rotates molecule about centre by this number of degrees,
        """
    @rotate.setter
    def rotate(*args, **kwargs):
        ...
    @property
    def scaleBondWidth(*args, **kwargs):
        """
        Scales the width of drawn bonds using image scaling.
        """
    @scaleBondWidth.setter
    def scaleBondWidth(*args, **kwargs):
        ...
    @property
    def scaleHighlightBondWidth(*args, **kwargs):
        """
        Scales the width of drawn highlighted bonds using image scaling.
        """
    @scaleHighlightBondWidth.setter
    def scaleHighlightBondWidth(*args, **kwargs):
        ...
    @property
    def scalingFactor(*args, **kwargs):
        """
        scaling factor for pixels->angstrom when auto scalingbeing used.  Default is 20.
        """
    @scalingFactor.setter
    def scalingFactor(*args, **kwargs):
        ...
    @property
    def simplifiedStereoGroupLabel(*args, **kwargs):
        """
        if all specified stereocenters are in a single StereoGroup, show a molecule-level annotation instead of the individual labels. Default is false.
        """
    @simplifiedStereoGroupLabel.setter
    def simplifiedStereoGroupLabel(*args, **kwargs):
        ...
    @property
    def singleColourWedgeBonds(*args, **kwargs):
        """
        if true wedged and dashed bonds are drawn using symbolColour rather than inheriting their colour from the atoms. Default is false.
        """
    @singleColourWedgeBonds.setter
    def singleColourWedgeBonds(*args, **kwargs):
        ...
    @property
    def splitBonds(*args, **kwargs):
        ...
    @splitBonds.setter
    def splitBonds(*args, **kwargs):
        ...
    @property
    def unspecifiedStereoIsUnknown(*args, **kwargs):
        """
        if true, double bonds with unspecified stereo are drawn crossed, potential stereocenters with unspecified stereo are drawn with a wavy bond. Default is false.
        """
    @unspecifiedStereoIsUnknown.setter
    def unspecifiedStereoIsUnknown(*args, **kwargs):
        ...
    @property
    def useComplexQueryAtomSymbols(*args, **kwargs):
        """
        replace any atom, any hetero, any halo queries with complex query symbols A, Q, X, M, optionally followed by H if hydrogen is included (except for AH, which stays *). Default is true
        """
    @useComplexQueryAtomSymbols.setter
    def useComplexQueryAtomSymbols(*args, **kwargs):
        ...
    @property
    def useMolBlockWedging(*args, **kwargs):
        """
        If the molecule came from a MolBlock, prefer the wedging information that provides.  If false, use RDKit rules.  Default false
        """
    @useMolBlockWedging.setter
    def useMolBlockWedging(*args, **kwargs):
        ...
    @property
    def variableAtomRadius(*args, **kwargs):
        """
        radius value to use for atoms involved in variable attachment points.
        """
    @variableAtomRadius.setter
    def variableAtomRadius(*args, **kwargs):
        ...
    @property
    def variableBondWidthMultiplier(*args, **kwargs):
        """
        what to multiply standard bond width by for variable attachment points.
        """
    @variableBondWidthMultiplier.setter
    def variableBondWidthMultiplier(*args, **kwargs):
        ...
class MultiColourHighlightStyle(Boost.Python.enum):
    CircleAndLine: typing.ClassVar[MultiColourHighlightStyle]  # value = rdkit.Chem.Draw.rdMolDraw2D.MultiColourHighlightStyle.CircleAndLine
    Lasso: typing.ClassVar[MultiColourHighlightStyle]  # value = rdkit.Chem.Draw.rdMolDraw2D.MultiColourHighlightStyle.Lasso
    __slots__: typing.ClassVar[tuple] = tuple()
    names: typing.ClassVar[dict]  # value = {'CircleAndLine': rdkit.Chem.Draw.rdMolDraw2D.MultiColourHighlightStyle.CircleAndLine, 'Lasso': rdkit.Chem.Draw.rdMolDraw2D.MultiColourHighlightStyle.Lasso}
    values: typing.ClassVar[dict]  # value = {0: rdkit.Chem.Draw.rdMolDraw2D.MultiColourHighlightStyle.CircleAndLine, 1: rdkit.Chem.Draw.rdMolDraw2D.MultiColourHighlightStyle.Lasso}
class map_indexing_suite_IntStringMap_entry(Boost.Python.instance):
    __instance_size__: typing.ClassVar[int] = 40
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    @staticmethod
    def __repr__(arg1: map_indexing_suite_IntStringMap_entry) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object __repr__(std::pair<int const, std::string>)
        """
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    def data(self) -> str:
        """
            C++ signature :
                std::string data(std::pair<int const, std::string> {lvalue})
        """
    def key(self) -> int:
        """
            C++ signature :
                int key(std::pair<int const, std::string> {lvalue})
        """
def ContourAndDrawGaussians(drawer: MolDraw2D, locs: typing.Any, heights: typing.Any, widths: typing.Any, nContours: int = 10, levels: typing.Any = None, params: ContourParams = ..., mol: typing.Any = None) -> None:
    """
        Generates and draws contours for a set of gaussians
        
          - drawer: the MolDraw2D object to use
          - locs: locations of the gaussians
          - heights: the heights (or weights) of the gaussians
          - widths: the standard deviations of the gaussians
          - nContours: the number of contours to draw
          - levels: the contours to use
          - ps: additional parameters controlling the contouring.
          - mol: molecule used to help set scale.
        
          The values are calculated on a grid with spacing params.gridResolution.
          If params.setScale  is set, the grid size will be calculated based on the
          locations of the gaussians and params.extraGridPadding. Otherwise the current
          size of the viewport will be used.
        
          If the levels argument is empty, the contour levels will be determined
          automatically from the max and min values on the grid and levels will
          be updated to include the contour levels.
        
          If params.fillGrid is set, the data on the grid will also be drawn using
          the color scheme in params.colourMap
        
          If mol is not 0, uses the molecule to help set the scale, assuming that
          it will be drawn over the plot, so needs to fit on it.
        */
    
        C++ signature :
            void ContourAndDrawGaussians(RDKit::MolDraw2D {lvalue},boost::python::api::object,boost::python::api::object,boost::python::api::object [,unsigned int=10 [,boost::python::api::object=None [,RDKit::MolDraw2DUtils::ContourParams=<rdkit.Chem.Draw.rdMolDraw2D.ContourParams object at 0x7f1efc725150> [,boost::python::api::object=None]]]])
    """
def ContourAndDrawGrid(drawer: MolDraw2D, data: typing.Any, xcoords: typing.Any, ycoords: typing.Any, nContours: int = 10, levels: typing.Any = None, params: ContourParams = ..., mol: typing.Any = None) -> None:
    """
        Generates and draws contours for data on a grid
        
          - drawer: the MolDraw2D object to use
          - data: numpy array with the data to be contoured
          - xcoords: the x coordinates of the grid
          - ycoords: the y coordinates of the grid
          - nContours: the number of contours to draw
          - levels: the contours to use
          - ps: additional parameters controlling the contouring
          - mol: molecule used to help set scale.
        
          The values are calculated on a grid with spacing params.gridResolution.
          If params.setScale  is set, the grid size will be calculated based on the
          locations of the gaussians and params.extraGridPadding. Otherwise the current
          size of the viewport will be used.
        
          If the levels argument is empty, the contour levels will be determined
          automatically from the max and min values on the grid and levels will
          be updated to include the contour levels.
        
          If params.fillGrid is set, the data on the grid will also be drawn using
          the color scheme in params.colourMap
        
          If mol is not 0, uses the molecule to help set the scale, assuming that
          it will be drawn over the plot, so needs to fit on it.
        */
    
        C++ signature :
            void ContourAndDrawGrid(RDKit::MolDraw2D {lvalue},boost::python::api::object {lvalue},boost::python::api::object {lvalue},boost::python::api::object {lvalue} [,unsigned int=10 [,boost::python::api::object {lvalue}=None [,RDKit::MolDraw2DUtils::ContourParams=<rdkit.Chem.Draw.rdMolDraw2D.ContourParams object at 0x7f1efc725220> [,boost::python::api::object=None]]]])
    """
def DrawMoleculeACS1996(drawer: MolDraw2D, mol: Mol, legend: str = '', highlightAtoms: typing.Any = None, highlightBonds: typing.Any = None, highlightAtomColors: typing.Any = None, highlightBondColors: typing.Any = None, highlightAtomRadii: typing.Any = None, confId: int = -1) -> None:
    """
        Draws molecule in ACS 1996 mode.
    
        C++ signature :
            void DrawMoleculeACS1996(RDKit::MolDraw2D {lvalue},RDKit::ROMol [,std::string='' [,boost::python::api::object=None [,boost::python::api::object=None [,boost::python::api::object=None [,boost::python::api::object=None [,boost::python::api::object=None [,int=-1]]]]]]])
    """
def MeanBondLength(mol: Mol, confId: int = -1) -> float:
    """
        Calculate the mean bond length for the molecule.
    
        C++ signature :
            double MeanBondLength(RDKit::ROMol [,int=-1])
    """
def MolToACS1996SVG(mol: Mol, legend: str = '', highlightAtoms: typing.Any = None, highlightBonds: typing.Any = None, highlightAtomColors: typing.Any = None, highlightBondColors: typing.Any = None, highlightAtomRadii: typing.Any = None, confId: int = -1) -> str:
    """
        Returns ACS 1996 mode svg for a molecule
    
        C++ signature :
            std::string MolToACS1996SVG(RDKit::ROMol [,std::string='' [,boost::python::api::object=None [,boost::python::api::object=None [,boost::python::api::object=None [,boost::python::api::object=None [,boost::python::api::object=None [,int=-1]]]]]]])
    """
def MolToSVG(mol: Mol, width: int = 300, height: int = 300, highlightAtoms: typing.Any = None, kekulize: bool = True, lineWidthMult: int = 1, fontSize: bool = 12, includeAtomCircles: int = True) -> str:
    """
        Returns svg for a molecule
    
        C++ signature :
            std::string MolToSVG(RDKit::ROMol [,unsigned int=300 [,unsigned int=300 [,boost::python::api::object=None [,bool=True [,unsigned int=1 [,bool=12 [,int=True]]]]]]])
    """
def PrepareAndDrawMolecule(drawer: MolDraw2D, mol: Mol, legend: str = '', highlightAtoms: typing.Any = None, highlightBonds: typing.Any = None, highlightAtomColors: typing.Any = None, highlightBondColors: typing.Any = None, highlightAtomRadii: typing.Any = None, confId: int = -1, kekulize: bool = True) -> None:
    """
        Preps a molecule for drawing and actually draws it
        
    
        C++ signature :
            void PrepareAndDrawMolecule(RDKit::MolDraw2D {lvalue},RDKit::ROMol [,std::string='' [,boost::python::api::object=None [,boost::python::api::object=None [,boost::python::api::object=None [,boost::python::api::object=None [,boost::python::api::object=None [,int=-1 [,bool=True]]]]]]]])
    """
def PrepareMolForDrawing(mol: Mol, kekulize: bool = True, addChiralHs: bool = True, wedgeBonds: bool = True, forceCoords: bool = False, wavyBonds: bool = False) -> rdkit.Chem.Mol:
    """
        Does some cleanup operations on the molecule to prepare it to draw nicely.
        The operations include: kekulization, addition of chiral Hs (so that we can draw
        wedges to them), wedging of bonds at chiral centers, and generation of a 2D
        conformation if the molecule does not already have a conformation
        
        Returns a modified copy of the molecule.
        
    
        C++ signature :
            RDKit::ROMol* PrepareMolForDrawing(RDKit::ROMol const* [,bool=True [,bool=True [,bool=True [,bool=False [,bool=False]]]]])
    """
def SetACS1996Mode(drawOptions: MolDrawOptions, meanBondLength: float) -> None:
    """
        Set the draw options to produce something as close as possible to
        the ACS 1996 guidelines as described at
        https://en.wikipedia.org/wiki/Wikipedia:Manual_of_Style/Chemistry/Structure_drawing
        
         - MolDrawOptions opt - the options what will be changed
         - float meanBondLength - mean bond length of the molecule
        
         Works best if the MolDraw2D object is created with width and height -1 (a
         flexiCanvas).
         The mean bond length may be calculated with MeanBondLength.
         It is used to calculate the offset for the lines in multiple bonds.
        
         Options changed are:
           bondLineWidth = 0.6
           scaleBondWidth = false
           scalingFactor = 14.4 / meanBondLen
           multipleBondOffset = 0.18
           highlightBondWidthMultiplier = 32
           setMonochromeMode - black and white
           fixedFontSize = 10
           additionalAtomLabelPadding = 0.066
           fontFile - if it isn't set already, then if RDBASE is set and the file
                      exists, uses $RDBASE/Data/Fonts/FreeSans.ttf.  Otherwise uses
                      BuiltinRobotoRegular.
         */
        
    
        C++ signature :
            void SetACS1996Mode(RDKit::MolDrawOptions {lvalue},double)
    """
@typing.overload
def SetDarkMode(d2d: MolDrawOptions) -> None:
    """
        set dark mode for a MolDrawOptions object
    
        C++ signature :
            void SetDarkMode(RDKit::MolDrawOptions {lvalue})
    """
@typing.overload
def SetDarkMode(d2d: MolDraw2D) -> None:
    """
        set dark mode for a MolDraw2D object
    
        C++ signature :
            void SetDarkMode(RDKit::MolDraw2D {lvalue})
    """
@typing.overload
def SetMonochromeMode(options: MolDrawOptions, fgColour: tuple, bgColour: tuple) -> None:
    """
        set monochrome mode for a MolDrawOptions object
    
        C++ signature :
            void SetMonochromeMode(RDKit::MolDrawOptions {lvalue},boost::python::tuple,boost::python::tuple)
    """
@typing.overload
def SetMonochromeMode(drawer: MolDraw2D, fgColour: tuple, bgColour: tuple) -> None:
    """
        set monochrome mode for a MolDraw2D object
    
        C++ signature :
            void SetMonochromeMode(RDKit::MolDraw2D {lvalue},boost::python::tuple,boost::python::tuple)
    """
def UpdateDrawerParamsFromJSON(drawer: MolDraw2D, json: str) -> None:
    """
        C++ signature :
            void UpdateDrawerParamsFromJSON(RDKit::MolDraw2D {lvalue},std::string)
    """
def UpdateMolDrawOptionsFromJSON(opts: MolDrawOptions, json: str) -> None:
    """
        C++ signature :
            void UpdateMolDrawOptionsFromJSON(RDKit::MolDrawOptions {lvalue},std::string)
    """
CircleAndLine: MultiColourHighlightStyle  # value = rdkit.Chem.Draw.rdMolDraw2D.MultiColourHighlightStyle.CircleAndLine
Lasso: MultiColourHighlightStyle  # value = rdkit.Chem.Draw.rdMolDraw2D.MultiColourHighlightStyle.Lasso
