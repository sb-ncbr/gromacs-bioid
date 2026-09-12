"""
Exposes the ForceField class
"""
from __future__ import annotations
import typing
__all__ = ['ForceField', 'MMFFMolProperties']
class ForceField(Boost.Python.instance):
    """
    A force field
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
    def AddDistanceConstraint(self, idx1: int, idx2: int, minLen: float, maxLen: float, forceConstant: float) -> None:
        """
            Adds a distance constraint to the UFF force field (deprecated, use UFFAddDistanceConstraint instead).
        
            C++ signature :
                void AddDistanceConstraint(ForceFields::PyForceField*,unsigned int,unsigned int,double,double,double)
        """
    def AddExtraPoint(self, x: float, y: float, z: float, fixed: bool = True) -> int:
        """
            Adds an extra point, this can be useful for adding constraints.
        
            C++ signature :
                int AddExtraPoint(ForceFields::PyForceField {lvalue},double,double,double [,bool=True])
        """
    def AddFixedPoint(self, idx: int) -> None:
        """
            Adds a fixed point to the force field.
        
            C++ signature :
                void AddFixedPoint(ForceFields::PyForceField*,unsigned int)
        """
    def CalcEnergy(self, pos: typing.Any = None) -> float:
        """
            Returns the energy (in kcal/mol) of the current arrangement
            or of the supplied coordinate list (if non-empty)
        
            C++ signature :
                double CalcEnergy(ForceFields::PyForceField {lvalue} [,boost::python::api::object=None])
        """
    def CalcGrad(self, pos: typing.Any = None) -> typing.Any:
        """
            Returns a tuple filled with the per-coordinate gradients
            of the current arrangement or of the supplied coordinate list (if non-empty)
        
            C++ signature :
                _object* CalcGrad(ForceFields::PyForceField {lvalue} [,boost::python::api::object=None])
        """
    def Dimension(self) -> int:
        """
            Returns the dimension of the ForceField
        
            C++ signature :
                unsigned int Dimension(ForceFields::PyForceField {lvalue})
        """
    def GetExtraPointPos(self, idx: int) -> typing.Any:
        """
            returns the location of an extra point as a tuple
        
            C++ signature :
                _object* GetExtraPointPos(ForceFields::PyForceField*,unsigned int)
        """
    def Initialize(self) -> None:
        """
            initializes the force field (call this before minimizing)
        
            C++ signature :
                void Initialize(ForceFields::PyForceField {lvalue})
        """
    def MMFFAddAngleConstraint(self, idx1: int, idx2: int, idx3: int, relative: bool, minAngleDeg: float, maxAngleDeg: float, forceConstant: float) -> None:
        """
            Adds an angle constraint to the MMFF force field; if relative == True, then minAngleDeg and maxAngleDeg are intended as relative to the current angle.
        
            C++ signature :
                void MMFFAddAngleConstraint(ForceFields::PyForceField*,unsigned int,unsigned int,unsigned int,bool,double,double,double)
        """
    def MMFFAddDistanceConstraint(self, idx1: int, idx2: int, relative: bool, minLen: float, maxLen: float, forceConstant: float) -> None:
        """
            Adds a distance constraint to the MMFF force field; if relative == True, then minLen and maxLen are intended as relative to the current distance.
        
            C++ signature :
                void MMFFAddDistanceConstraint(ForceFields::PyForceField*,unsigned int,unsigned int,bool,double,double,double)
        """
    def MMFFAddPositionConstraint(self, idx: int, maxDispl: float, forceConstant: float) -> None:
        """
            Adds a position constraint to the MMFF force field.
        
            C++ signature :
                void MMFFAddPositionConstraint(ForceFields::PyForceField*,unsigned int,double,double)
        """
    def MMFFAddTorsionConstraint(self, idx1: int, idx2: int, idx3: int, idx4: int, relative: bool, minDihedralDeg: float, maxDihedralDeg: float, forceConstant: float) -> None:
        """
            Adds a dihedral angle constraint to the MMFF force field; if relative == True, then minDihedralDeg and maxDihedralDeg are intended as relative to the current dihedral angle.
        
            C++ signature :
                void MMFFAddTorsionConstraint(ForceFields::PyForceField*,unsigned int,unsigned int,unsigned int,unsigned int,bool,double,double,double)
        """
    def Minimize(self, maxIts: int = 200, forceTol: float = 0.0001, energyTol: float = 1e-06) -> int:
        """
            Runs some minimization iterations.
            
              Returns 0 if the minimization succeeded.
        
            C++ signature :
                int Minimize(ForceFields::PyForceField {lvalue} [,int=200 [,double=0.0001 [,double=1e-06]]])
        """
    def MinimizeTrajectory(self, snapshotFreq: int, maxIts: int = 200, forceTol: float = 0.0001, energyTol: float = 1e-06) -> tuple:
        """
            Runs some minimization iterations, recording the minimization trajectory every snapshotFreq steps.
            
            Returns a (int, []) tuple; the int is 0 if the minimization succeeded, while the list contains Snapshot objects.
        
            C++ signature :
                boost::python::tuple MinimizeTrajectory(ForceFields::PyForceField {lvalue},unsigned int [,int=200 [,double=0.0001 [,double=1e-06]]])
        """
    def NumPoints(self) -> int:
        """
            Returns the number of points the ForceField is handling
        
            C++ signature :
                unsigned int NumPoints(ForceFields::PyForceField {lvalue})
        """
    def Positions(self) -> typing.Any:
        """
            Returns a tuple filled with the coordinates of the
            points the ForceField is handling
        
            C++ signature :
                _object* Positions(ForceFields::PyForceField {lvalue})
        """
    def UFFAddAngleConstraint(self, idx1: int, idx2: int, idx3: int, relative: bool, minAngleDeg: float, maxAngleDeg: float, forceConstant: float) -> None:
        """
            Adds an angle constraint to the UFF force field; if relative == True, then minAngleDeg and maxAngleDeg are intended as relative to the current angle.
        
            C++ signature :
                void UFFAddAngleConstraint(ForceFields::PyForceField*,unsigned int,unsigned int,unsigned int,bool,double,double,double)
        """
    def UFFAddDistanceConstraint(self, idx1: int, idx2: int, relative: bool, minLen: float, maxLen: float, forceConstant: float) -> None:
        """
            Adds a distance constraint to the UFF force field; if relative == True, then minLen and maxLen are intended as relative to the current distance.
        
            C++ signature :
                void UFFAddDistanceConstraint(ForceFields::PyForceField*,unsigned int,unsigned int,bool,double,double,double)
        """
    def UFFAddPositionConstraint(self, idx: int, maxDispl: float, forceConstant: float) -> None:
        """
            Adds a position constraint to the UFF force field.
        
            C++ signature :
                void UFFAddPositionConstraint(ForceFields::PyForceField*,unsigned int,double,double)
        """
    def UFFAddTorsionConstraint(self, idx1: int, idx2: int, idx3: int, idx4: int, relative: bool, minDihedralDeg: float, maxDihedralDeg: float, forceConstant: float) -> None:
        """
            Adds a dihedral angle constraint to the UFF force field; if relative == True, then minDihedralDeg and maxDihedralDeg are intended as relative to the current dihedral angle.
        
            C++ signature :
                void UFFAddTorsionConstraint(ForceFields::PyForceField*,unsigned int,unsigned int,unsigned int,unsigned int,bool,double,double,double)
        """
class MMFFMolProperties(Boost.Python.instance):
    """
    MMFF molecular properties
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
    def GetMMFFAngleBendParams(self, mol: typing.Any, idx1: int, idx2: int, idx3: int) -> typing.Any:
        """
            Retrieves MMFF angle bend parameters for atoms with indexes idx1, idx2, idx3 as a (angleType, ka, theta0) tuple, or None if no parameters could be found
        
            C++ signature :
                _object* GetMMFFAngleBendParams(ForceFields::PyMMFFMolProperties {lvalue},RDKit::ROMol,unsigned int,unsigned int,unsigned int)
        """
    def GetMMFFAtomType(self, idx: int) -> int:
        """
            Retrieves MMFF atom type for atom with index idx
        
            C++ signature :
                unsigned int GetMMFFAtomType(ForceFields::PyMMFFMolProperties {lvalue},unsigned int)
        """
    def GetMMFFBondStretchParams(self, mol: typing.Any, idx1: int, idx2: int) -> typing.Any:
        """
            Retrieves MMFF bond stretch parameters for atoms with indexes idx1, idx2 as a (bondType, kb, r0) tuple, or None if no parameters could be found
        
            C++ signature :
                _object* GetMMFFBondStretchParams(ForceFields::PyMMFFMolProperties {lvalue},RDKit::ROMol,unsigned int,unsigned int)
        """
    def GetMMFFFormalCharge(self, idx: int) -> float:
        """
            Retrieves MMFF formal charge for atom with index idx
        
            C++ signature :
                double GetMMFFFormalCharge(ForceFields::PyMMFFMolProperties {lvalue},unsigned int)
        """
    def GetMMFFOopBendParams(self, mol: typing.Any, idx1: int, idx2: int, idx3: int, idx4: int) -> typing.Any:
        """
            Retrieves MMFF out-of-plane bending force constant for atoms with indexes idx1, idx2, idx3, idx4 as a koop float value
        
            C++ signature :
                _object* GetMMFFOopBendParams(ForceFields::PyMMFFMolProperties {lvalue},RDKit::ROMol,unsigned int,unsigned int,unsigned int,unsigned int)
        """
    def GetMMFFPartialCharge(self, idx: int) -> float:
        """
            Retrieves MMFF partial charge for atom with index idx
        
            C++ signature :
                double GetMMFFPartialCharge(ForceFields::PyMMFFMolProperties {lvalue},unsigned int)
        """
    def GetMMFFStretchBendParams(self, mol: typing.Any, idx1: int, idx2: int, idx3: int) -> typing.Any:
        """
            Retrieves MMFF stretch-bend parameters for atoms with indexes idx1, idx2, idx3 as a (stretchBendType, kbaIJK, kbaKJI) tuple, or None if no parameters could be found
        
            C++ signature :
                _object* GetMMFFStretchBendParams(ForceFields::PyMMFFMolProperties {lvalue},RDKit::ROMol,unsigned int,unsigned int,unsigned int)
        """
    def GetMMFFTorsionParams(self, mol: typing.Any, idx1: int, idx2: int, idx3: int, idx4: int) -> typing.Any:
        """
            Retrieves MMFF torsion parameters for atoms with indexes idx1, idx2, idx3, idx4 as a (torsionType, V1, V2, V3) tuple, or None if no parameters could be found
        
            C++ signature :
                _object* GetMMFFTorsionParams(ForceFields::PyMMFFMolProperties {lvalue},RDKit::ROMol,unsigned int,unsigned int,unsigned int,unsigned int)
        """
    def GetMMFFVdWParams(self, idx1: int, idx2: int) -> typing.Any:
        """
            Retrieves MMFF van der Waals parameters for atoms with indexes idx1, idx2 as a (R_ij_starUnscaled, epsilonUnscaled, R_ij_star, epsilon) tuple, or None if no parameters could be found
        
            C++ signature :
                _object* GetMMFFVdWParams(ForceFields::PyMMFFMolProperties {lvalue},unsigned int,unsigned int)
        """
    def SetMMFFAngleTerm(self, state: bool = True) -> None:
        """
            Sets the angle term to be included in the MMFF equation (defaults to True)
        
            C++ signature :
                void SetMMFFAngleTerm(ForceFields::PyMMFFMolProperties {lvalue} [,bool=True])
        """
    def SetMMFFBondTerm(self, state: bool = True) -> None:
        """
            Sets the bond term to be included in the MMFF equation (defaults to True)
        
            C++ signature :
                void SetMMFFBondTerm(ForceFields::PyMMFFMolProperties {lvalue} [,bool=True])
        """
    def SetMMFFDielectricConstant(self, dielConst: float = 1.0) -> None:
        """
            Sets the DielConst MMFF property (defaults to 1.0)
        
            C++ signature :
                void SetMMFFDielectricConstant(ForceFields::PyMMFFMolProperties {lvalue} [,double=1.0])
        """
    def SetMMFFDielectricModel(self, dielModel: int = 1) -> None:
        """
            Sets the DielModel MMFF property (1: constant; 2: distance-dependent; defaults to constant)
        
            C++ signature :
                void SetMMFFDielectricModel(ForceFields::PyMMFFMolProperties {lvalue} [,unsigned char=1])
        """
    def SetMMFFEleTerm(self, state: bool = True) -> None:
        """
            Sets the electrostatic term to be included in the MMFF equation (defaults to True)
        
            C++ signature :
                void SetMMFFEleTerm(ForceFields::PyMMFFMolProperties {lvalue} [,bool=True])
        """
    def SetMMFFOopTerm(self, state: bool = True) -> None:
        """
            Sets the out-of-plane bend term to be included in the MMFF equation (defaults to True)
        
            C++ signature :
                void SetMMFFOopTerm(ForceFields::PyMMFFMolProperties {lvalue} [,bool=True])
        """
    def SetMMFFStretchBendTerm(self, state: bool = True) -> None:
        """
            Sets the stretch-bend term to be included in the MMFF equation (defaults to True)
        
            C++ signature :
                void SetMMFFStretchBendTerm(ForceFields::PyMMFFMolProperties {lvalue} [,bool=True])
        """
    def SetMMFFTorsionTerm(self, state: bool = True) -> None:
        """
            Sets the torsional term to be included in the MMFF equation (defaults to True)
        
            C++ signature :
                void SetMMFFTorsionTerm(ForceFields::PyMMFFMolProperties {lvalue} [,bool=True])
        """
    def SetMMFFVariant(self, mmffVariant: str = 'MMFF94') -> None:
        """
            Sets the MMFF variant to be used ("MMFF94" or "MMFF94s"; defaults to "MMFF94")
        
            C++ signature :
                void SetMMFFVariant(ForceFields::PyMMFFMolProperties {lvalue} [,std::string='MMFF94'])
        """
    def SetMMFFVdWTerm(self, state: bool = True) -> None:
        """
            Sets the Van der Waals term to be included in the MMFF equation (defaults to True)
        
            C++ signature :
                void SetMMFFVdWTerm(ForceFields::PyMMFFMolProperties {lvalue} [,bool=True])
        """
    def SetMMFFVerbosity(self, verbosity: int = 0) -> None:
        """
            Sets the MMFF verbosity (0: none; 1: low; 2: high; defaults to 0)
        
            C++ signature :
                void SetMMFFVerbosity(ForceFields::PyMMFFMolProperties {lvalue} [,unsigned int=0])
        """
