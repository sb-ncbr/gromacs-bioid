"""
PathSimAnalysis
Calculates the geometric similarity of molecular dynamics trajectories using path metrics such as the Hausdorff and Fréchet distances.
"""

# Add imports here
from .psa import *

from MDAnalysis.due import due, Doi

due.cite(Doi("10.1371/journal.pcbi.1004568"),
         description="Path Similarity Analysis algorithm and implementation",
         path="pathsimanalysis.psa",
         cite_module=True)
del Doi

# Handle version
from importlib.metadata import version
__version__ = version("pathsimanalysis")
