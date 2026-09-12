"""
 Configuration for the RDKit Python code

"""
from __future__ import annotations
import os as os
import rdkit as rdkit
import sqlite3 as sqlite3
import sys as sys
__all__ = ['ObsoleteCodeError', 'RDCodeDir', 'RDContribDir', 'RDDataDatabase', 'RDDataDir', 'RDDocsDir', 'RDProjDir', 'RDTestDatabase', 'UnimplementedCodeError', 'defaultDBPassword', 'defaultDBUser', 'molViewer', 'os', 'pythonExe', 'pythonTestCommand', 'rdkit', 'rpcTestPort', 'sqlite3', 'sys', 'usePgSQL', 'useSqlLite']
class ObsoleteCodeError(Exception):
    pass
class UnimplementedCodeError(Exception):
    pass
RDCodeDir: str = '/project/build/temp.linux-x86_64-cpython-311/rdkit_install/lib/python3.11/site-packages/rdkit'
RDContribDir: str = '/project/build/temp.linux-x86_64-cpython-311/rdkit_install/share/RDKit/Contrib'
RDDataDatabase: str = '/project/build/temp.linux-x86_64-cpython-311/rdkit_install/share/RDKit/Data/RDData.sqlt'
RDDataDir: str = '/project/build/temp.linux-x86_64-cpython-311/rdkit_install/share/RDKit/Data'
RDDocsDir: str = '/project/build/temp.linux-x86_64-cpython-311/rdkit_install/share/RDKit/Docs'
RDProjDir: str = '/project/build/temp.linux-x86_64-cpython-311/rdkit_install/share/RDKit/Projects'
RDTestDatabase: str = '/project/build/temp.linux-x86_64-cpython-311/rdkit_install/share/RDKit/Data/RDTests.sqlt'
defaultDBPassword: str = 'masterkey'
defaultDBUser: str = 'sysdba'
molViewer: str = 'PYMOL'
pythonExe: str = '/opt/python/cp311-cp311/bin/python3.11'
pythonTestCommand: str = 'python'
rpcTestPort: int = 8423
usePgSQL: bool = False
useSqlLite: bool = True
