/**
 * Copyright (c) 2020-2021 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
import { PresetProvider } from '../preset-provider';
import { PluginStateObject } from '../../objects';
import { ParamDefinition as PD } from '../../../mol-util/param-definition';
import { StateTransformer } from '../../../mol-state';
import { PluginContext } from '../../../mol-plugin/context';
export interface TrajectoryHierarchyPresetProvider<P = any, S = {}> extends PresetProvider<PluginStateObject.Molecule.Trajectory, P, S> {
}
export declare function TrajectoryHierarchyPresetProvider<P, S>(preset: TrajectoryHierarchyPresetProvider<P, S>): TrajectoryHierarchyPresetProvider<P, S>;
export declare namespace TrajectoryHierarchyPresetProvider {
    type Params<P extends TrajectoryHierarchyPresetProvider> = P extends TrajectoryHierarchyPresetProvider<infer T> ? T : never;
    type State<P extends TrajectoryHierarchyPresetProvider> = P extends TrajectoryHierarchyPresetProvider<infer _, infer S> ? S : never;
    const CommonParams: (a: PluginStateObject.Molecule.Trajectory | undefined, plugin: PluginContext) => {
        modelProperties: PD.Base<PD.Normalize<PD.Normalize<{
            autoAttach: string[];
            properties: PD.Normalize<{
                [x: string]: /*elided*/ any;
            }>;
        }>> | undefined>;
        structureProperties: PD.Base<PD.Normalize<PD.Normalize<{
            autoAttach: string[];
            properties: PD.Normalize<{
                [x: string]: /*elided*/ any;
            }>;
        }>> | undefined>;
        representationPreset: PD.Base<"auto" | "empty" | "illustrative" | "molecular-surface" | "atomic-detail" | "polymer-cartoon" | "polymer-and-ligand" | "protein-and-nucleic" | "coarse-surface" | "auto-lod" | undefined>;
    };
}
export declare const PresetTrajectoryHierarchy: {
    default: TrajectoryHierarchyPresetProvider<{
        modelProperties: PD.Normalize<PD.Normalize<{
            autoAttach: /*elided*/ any;
            properties: /*elided*/ any;
        }>> | undefined;
        structureProperties: PD.Normalize<PD.Normalize<{
            autoAttach: /*elided*/ any;
            properties: /*elided*/ any;
        }>> | undefined;
        representationPreset: "auto" | "empty" | "illustrative" | "molecular-surface" | "atomic-detail" | "polymer-cartoon" | "polymer-and-ligand" | "protein-and-nucleic" | "coarse-surface" | "auto-lod" | undefined;
        model: PD.Normalize<PD.Normalize<{
            modelIndex: /*elided*/ any;
        }>> | undefined;
        showUnitcell: boolean | undefined;
        structure: PD.NamedParams<PD.Normalize<{
            dynamicBonds: /*elided*/ any;
        }>, "auto"> | PD.NamedParams<PD.Normalize<{
            dynamicBonds: /*elided*/ any;
            id: /*elided*/ any;
        }>, "assembly"> | PD.NamedParams<PD.Normalize<{
            dynamicBonds: /*elided*/ any;
            ijkMin: /*elided*/ any;
            ijkMax: /*elided*/ any;
        }>, "symmetry"> | PD.NamedParams<PD.Normalize<{
            dynamicBonds: /*elided*/ any;
        }>, "model"> | PD.NamedParams<PD.Normalize<{
            dynamicBonds: /*elided*/ any;
            radius: /*elided*/ any;
        }>, "symmetry-mates"> | PD.NamedParams<PD.Normalize<{
            dynamicBonds: /*elided*/ any;
            generators: /*elided*/ any;
        }>, "symmetry-assembly"> | undefined;
        representationPresetParams: PD.Normalize<{
            ignoreHydrogens: /*elided*/ any;
            ignoreHydrogensVariant: /*elided*/ any;
            ignoreLight: /*elided*/ any;
            quality: /*elided*/ any;
            theme: /*elided*/ any;
        }> | undefined;
    }, {
        model: import("../../../mol-state").StateObjectSelector<PluginStateObject.Molecule.Model, StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>>;
        modelProperties: import("../../../mol-state").StateObjectSelector<PluginStateObject.Molecule.Model, StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>>;
        unitcell: import("../../../mol-state").StateObjectSelector<PluginStateObject.Shape.Representation3D, StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>> | undefined;
        structure: import("../../../mol-state").StateObjectSelector<PluginStateObject.Molecule.Structure, StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>>;
        structureProperties: import("../../../mol-state").StateObjectSelector<PluginStateObject.Molecule.Structure, StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>>;
        representation: any;
    }>;
    'all-models': TrajectoryHierarchyPresetProvider<{
        modelProperties: PD.Normalize<PD.Normalize<{
            autoAttach: /*elided*/ any;
            properties: /*elided*/ any;
        }>> | undefined;
        structureProperties: PD.Normalize<PD.Normalize<{
            autoAttach: /*elided*/ any;
            properties: /*elided*/ any;
        }>> | undefined;
        representationPreset: "auto" | "empty" | "illustrative" | "molecular-surface" | "atomic-detail" | "polymer-cartoon" | "polymer-and-ligand" | "protein-and-nucleic" | "coarse-surface" | "auto-lod" | undefined;
        useDefaultIfSingleModel: boolean | undefined;
        representationPresetParams: PD.Normalize<{
            ignoreHydrogens: /*elided*/ any;
            ignoreHydrogensVariant: /*elided*/ any;
            ignoreLight: /*elided*/ any;
            quality: /*elided*/ any;
            theme: /*elided*/ any;
        }> | undefined;
    }, {
        model: import("../../../mol-state").StateObjectSelector<PluginStateObject.Molecule.Model, StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>>;
        modelProperties: import("../../../mol-state").StateObjectSelector<PluginStateObject.Molecule.Model, StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>>;
        unitcell: import("../../../mol-state").StateObjectSelector<PluginStateObject.Shape.Representation3D, StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>> | undefined;
        structure: import("../../../mol-state").StateObjectSelector<PluginStateObject.Molecule.Structure, StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>>;
        structureProperties: import("../../../mol-state").StateObjectSelector<PluginStateObject.Molecule.Structure, StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>>;
        representation: any;
    } | {
        models?: undefined;
        structures?: undefined;
    } | {
        models: import("../../../mol-state").StateObjectSelector<PluginStateObject.Molecule.Model, StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>>[];
        structures: import("../../../mol-state").StateObjectSelector<PluginStateObject.Molecule.Structure, StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>>[];
    }>;
    unitcell: TrajectoryHierarchyPresetProvider<{
        modelProperties: PD.Normalize<PD.Normalize<{
            autoAttach: /*elided*/ any;
            properties: /*elided*/ any;
        }>> | undefined;
        structureProperties: PD.Normalize<PD.Normalize<{
            autoAttach: /*elided*/ any;
            properties: /*elided*/ any;
        }>> | undefined;
        representationPreset: "auto" | "empty" | "illustrative" | "molecular-surface" | "atomic-detail" | "polymer-cartoon" | "polymer-and-ligand" | "protein-and-nucleic" | "coarse-surface" | "auto-lod" | undefined;
        model: PD.Normalize<PD.Normalize<{
            modelIndex: /*elided*/ any;
        }>> | undefined;
    }, {
        model: import("../../../mol-state").StateObjectSelector<PluginStateObject.Molecule.Model, StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>>;
        modelProperties: import("../../../mol-state").StateObjectSelector<PluginStateObject.Molecule.Model, StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>>;
        unitcell: import("../../../mol-state").StateObjectSelector<PluginStateObject.Shape.Representation3D, StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>> | undefined;
        structure: import("../../../mol-state").StateObjectSelector<PluginStateObject.Molecule.Structure, StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>>;
        structureProperties: import("../../../mol-state").StateObjectSelector<PluginStateObject.Molecule.Structure, StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>>;
        representation: any;
    }>;
    supercell: TrajectoryHierarchyPresetProvider<{
        modelProperties: PD.Normalize<PD.Normalize<{
            autoAttach: /*elided*/ any;
            properties: /*elided*/ any;
        }>> | undefined;
        structureProperties: PD.Normalize<PD.Normalize<{
            autoAttach: /*elided*/ any;
            properties: /*elided*/ any;
        }>> | undefined;
        representationPreset: "auto" | "empty" | "illustrative" | "molecular-surface" | "atomic-detail" | "polymer-cartoon" | "polymer-and-ligand" | "protein-and-nucleic" | "coarse-surface" | "auto-lod" | undefined;
        model: PD.Normalize<PD.Normalize<{
            modelIndex: /*elided*/ any;
        }>> | undefined;
    }, {
        model: import("../../../mol-state").StateObjectSelector<PluginStateObject.Molecule.Model, StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>>;
        modelProperties: import("../../../mol-state").StateObjectSelector<PluginStateObject.Molecule.Model, StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>>;
        unitcell: import("../../../mol-state").StateObjectSelector<PluginStateObject.Shape.Representation3D, StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>> | undefined;
        structure: import("../../../mol-state").StateObjectSelector<PluginStateObject.Molecule.Structure, StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>>;
        structureProperties: import("../../../mol-state").StateObjectSelector<PluginStateObject.Molecule.Structure, StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>>;
        representation: any;
    }>;
    crystalContacts: TrajectoryHierarchyPresetProvider<{
        modelProperties: PD.Normalize<PD.Normalize<{
            autoAttach: /*elided*/ any;
            properties: /*elided*/ any;
        }>> | undefined;
        structureProperties: PD.Normalize<PD.Normalize<{
            autoAttach: /*elided*/ any;
            properties: /*elided*/ any;
        }>> | undefined;
        representationPreset: "auto" | "empty" | "illustrative" | "molecular-surface" | "atomic-detail" | "polymer-cartoon" | "polymer-and-ligand" | "protein-and-nucleic" | "coarse-surface" | "auto-lod" | undefined;
        model: PD.Normalize<PD.Normalize<{
            modelIndex: /*elided*/ any;
        }>> | undefined;
    }, {
        model: import("../../../mol-state").StateObjectSelector<PluginStateObject.Molecule.Model, StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>>;
        modelProperties: import("../../../mol-state").StateObjectSelector<PluginStateObject.Molecule.Model, StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>>;
        unitcell: import("../../../mol-state").StateObjectSelector<PluginStateObject.Shape.Representation3D, StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>> | undefined;
        structure: import("../../../mol-state").StateObjectSelector<PluginStateObject.Molecule.Structure, StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>>;
        structureProperties: import("../../../mol-state").StateObjectSelector<PluginStateObject.Molecule.Structure, StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>>;
        representation: any;
    }>;
};
export type PresetTrajectoryHierarchy = typeof PresetTrajectoryHierarchy;
