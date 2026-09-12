/**
 * Copyright (c) 2020 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
import { PluginContext } from '../../../mol-plugin/context';
import { StateObjectRef } from '../../../mol-state';
import { ParamDefinition as PD } from '../../../mol-util/param-definition';
import { PluginStateObject } from '../../objects';
import { PresetTrajectoryHierarchy, TrajectoryHierarchyPresetProvider } from './hierarchy-preset';
export type TrajectoryHierarchyPresetProviderRef = keyof PresetTrajectoryHierarchy | TrajectoryHierarchyPresetProvider | string;
export declare class TrajectoryHierarchyBuilder {
    plugin: PluginContext;
    private _providers;
    private providerMap;
    readonly defaultProvider: TrajectoryHierarchyPresetProvider<{
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
        model: import("../../../mol-state").StateObjectSelector<PluginStateObject.Molecule.Model, import("../../../mol-state").StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>>;
        modelProperties: import("../../../mol-state").StateObjectSelector<PluginStateObject.Molecule.Model, import("../../../mol-state").StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>>;
        unitcell: import("../../../mol-state").StateObjectSelector<PluginStateObject.Shape.Representation3D, import("../../../mol-state").StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>> | undefined;
        structure: import("../../../mol-state").StateObjectSelector<PluginStateObject.Molecule.Structure, import("../../../mol-state").StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>>;
        structureProperties: import("../../../mol-state").StateObjectSelector<PluginStateObject.Molecule.Structure, import("../../../mol-state").StateTransformer<import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, import("../../../mol-state").StateObject<any, import("../../../mol-state").StateObject.Type<any>>, any>>;
        representation: any;
    }>;
    private resolveProvider;
    hasPreset(t: PluginStateObject.Molecule.Trajectory): boolean;
    get providers(): ReadonlyArray<TrajectoryHierarchyPresetProvider>;
    getPresets(t?: PluginStateObject.Molecule.Trajectory): readonly TrajectoryHierarchyPresetProvider<any, {}>[];
    getPresetSelect(t?: PluginStateObject.Molecule.Trajectory): PD.Select<string>;
    getPresetsWithOptions(t: PluginStateObject.Molecule.Trajectory): PD.Mapped<PD.NamedParams<any, string>>;
    registerPreset(provider: TrajectoryHierarchyPresetProvider): void;
    unregisterPreset(provider: TrajectoryHierarchyPresetProvider): void;
    applyPreset<K extends keyof PresetTrajectoryHierarchy>(parent: StateObjectRef<PluginStateObject.Molecule.Trajectory>, preset: K, params?: Partial<TrajectoryHierarchyPresetProvider.Params<PresetTrajectoryHierarchy[K]>>): Promise<TrajectoryHierarchyPresetProvider.State<PresetTrajectoryHierarchy[K]>> | undefined;
    applyPreset<P = any, S = {}>(parent: StateObjectRef<PluginStateObject.Molecule.Trajectory>, provider: TrajectoryHierarchyPresetProvider<P, S>, params?: P): Promise<S> | undefined;
    constructor(plugin: PluginContext);
}
