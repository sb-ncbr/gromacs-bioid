/**
 * Copyright (c) 2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Adam Midlik <midlik@gmail.com>
 */
import { PluginStateObject as SO } from '../../../mol-plugin-state/objects';
import { ParamDefinition as PD } from '../../../mol-util/param-definition';
export declare const StructureSurroundingsParams: {
    radius: PD.Numeric;
    includeSelf: PD.BooleanParam;
    wholeResidues: PD.BooleanParam;
    nullIfEmpty: PD.Base<boolean | undefined>;
};
export type StructureSurroundingsParams = typeof StructureSurroundingsParams;
export type StructureSurroundingsProps = PD.ValuesFor<StructureSurroundingsParams>;
export type StructureSurroundings = typeof StructureSurroundings;
export declare const StructureSurroundings: import("../../../mol-state").StateTransformer<SO.Molecule.Structure, SO.Molecule.Structure, PD.Normalize<{
    radius: number;
    includeSelf: boolean;
    wholeResidues: boolean;
    nullIfEmpty: boolean | undefined;
}>>;
