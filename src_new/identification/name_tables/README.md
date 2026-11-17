# Force-field name table

`maps.json` maps force-field residue / moleculetype names, exactly as they
appear in topology files (`POPC`, `CHL1`, `TOCL2`, `SOD`, `CLA`, `Na+`, `NA`,
...), to the InChIKey of the molecule they denote. `maps_provenance.json`
holds one record per key: molecule, force fields, InChIKey, PubChem CID,
formula, source URLs and notes.

## How it is used

`NameResolverMAPS` (`resolvers/name.py`, config `[names] maps_db`) looks the
signature up with an exact, case-sensitive `dict.get` and returns the value as
one InChIKey candidate. That candidate has the **same weight as every other
identity candidate**. It is resolved to a structure and must pass the normal
heavy-atom skeleton verification (Tanimoto >= 0.7). It is **never an
override**. For example, the `CLA` entry (chloride) competes with the CCD
`CLA` (chlorophyll a), and verification picks the one that matches the
simulated atoms.

The table is not wired into `config.ini`. To use it, point
`[names] maps_db` at `src_new/identification/name_tables/maps.json`.

## What is in it

- **CHARMM36 lipids, sterols, detergents and fatty acids**, read from the
  official toppar (`toppar_c36_jul24`). Each structure was built from the RTF
  bonds, so InChIKey block 1 (connectivity) is the topology's own.
  - Stereo comes from the IC table and is then set to the natural form the
    residue documents: sn-glycero-3, L-serine, 1'-sn-glycerol PG head, Z acyl
    C=C, (2S,3R,4E) sphingoid base and 1D-myo-inositol.
  - Each key keeps the CHARMM charge state when PubChem has it. Otherwise it
    uses the neutral parent; the notes say which.
- **Ion names** from CHARMM (`SOD`, `POT`, `CLA`, ...), AMBER leap libraries
  (`Na+`, `Cl-`, `K+`, `Li+`, `Rb+`, `Cs+`, `MG2`, `IOD`) and GROMACS
  `ions.itp` (`NA`, `CL`, `K`, `MG`, `CA`, `ZN`, ...). Each maps to the
  charged ion.
- **Cholesterol** under the Slipids (`CHOL`) and AMBER Lipid14/17/21 (`CHL`)
  names.

The table never includes:

- water names (water segments are skipped before identification)
- protein residue variants (`HSD`, `HIE`, `CYX`, ...)
- coarse-grained (Martini) names
- any name whose structure could not be resolved on PubChem

## Adding an entry

1. Find the residue in an authoritative topology (CHARMM toppar, AMBER leap
   library, GROMACS `.itp`) and confirm its structure: bonds, charge and,
   where it matters, stereo.
2. Pick the PubChem record for that structure. Prefer the force field's charge
   state; otherwise use the neutral parent.
3. Add the key to `maps.json`, keeping the keys sorted. Add a matching record
   to `maps_provenance.json` with `name`, `molecule`, `forcefields`,
   `inchikey`, `pubchem_cid`, `formula` (PubChem's `MolecularFormula`),
   `source_urls` (the topology source and the PubChem compound page) and
   `notes`.
4. Run the network check, then the offline tests:

   ```
   .venv/bin/python src_new/identification/name_tables/validate.py
   .venv/bin/python -m pytest -q -p no:cacheprovider tests/src_new/identification/test_name_tables.py
   ```

## Cache

Resolver results are cached per resolver name and signature in the
identifiers cache (`[identifiers_cache]`, `resolver_cache.sqlite3`; also the
shared cache if one is configured). After you change or remove a mapping,
clear the cached `name_maps` rows, or the whole cache. Otherwise old answers
keep being served.
