/**
 * Copyright (c) 2023 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Sebastian Bittrich <sebastian.bittrich@rcsb.org>
 */
import { PluginStateObject } from '../../../mol-plugin-state/objects';
import { ParamDefinition as PD } from '../../../mol-util/param-definition';
import { StructureRepresentationPresetProvider } from '../../../mol-plugin-state/builder/structure/representation-preset';
import { CCDFormat } from '../../../mol-model-formats/structure/mmcif';
import { TrajectoryHierarchyPresetProvider } from '../../../mol-plugin-state/builder/structure/hierarchy-preset';
export declare const ChemicalCompontentTrajectoryHierarchyPreset: TrajectoryHierarchyPresetProvider<{
    modelProperties: PD.Normalize<PD.Normalize<{
        autoAttach: /*elided*/ any;
        properties: /*elided*/ any;
    }>> | undefined;
    structureProperties: PD.Normalize<PD.Normalize<{
        autoAttach: /*elided*/ any;
        properties: /*elided*/ any;
    }>> | undefined;
    representationPreset: "auto" | "empty" | "illustrative" | "molecular-surface" | "atomic-detail" | "polymer-cartoon" | "polymer-and-ligand" | "protein-and-nucleic" | "coarse-surface" | "auto-lod" | undefined;
    representationPresetParams: PD.Normalize<{
        ignoreHydrogens: /*elided*/ any;
        ignoreHydrogensVariant: /*elided*/ any;
        ignoreLight: /*elided*/ any;
        quality: /*elided*/ any;
        theme: /*elided*/ any;
    }> | undefined;
    showOriginalCoordinates: boolean | undefined;
    shownCoordinateType: "both" | "model" | "ideal";
    aromaticBonds: boolean;
}, {
    models?: undefined;
    structures?: undefined;
} | {
    models: import("../../../mol-state").StateObjectSelector<PluginStateObject.Molecule.Model, import("../../../mol-state").StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>>[];
    structures: import("../../../mol-state").StateObjectSelector<PluginStateObject.Molecule.Structure, import("../../../mol-state").StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>>[];
}>;
export declare const ChemicalComponentPreset: StructureRepresentationPresetProvider<{
    aromaticBonds: boolean;
    coordinateType: CCDFormat.CoordinateType;
    isHidden: boolean;
    ignoreHydrogens: boolean | undefined;
    ignoreHydrogensVariant: "all" | "non-polar" | undefined;
    ignoreLight: boolean | undefined;
    quality: "auto" | "medium" | "high" | "low" | "custom" | "highest" | "higher" | "lower" | "lowest" | undefined;
    theme: PD.Normalize<{
        globalName: /*elided*/ any;
        globalColorParams: /*elided*/ any;
        carbonColor: /*elided*/ any;
        symmetryColor: /*elided*/ any;
        symmetryColorParams: /*elided*/ any;
        focus: /*elided*/ any;
    }> | undefined;
}, {
    components?: undefined;
    representations?: undefined;
} | {
    components: {
        [x: string]: import("../../../mol-state").StateObjectSelector<PluginStateObject.Molecule.Structure, import("../../../mol-state").StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>> | undefined;
    };
    representations: {
        [x: string]: import("../../../mol-state").StateObjectSelector<PluginStateObject.Molecule.Structure.Representation3D, import("../../../mol-state").StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>>;
    };
}>;
