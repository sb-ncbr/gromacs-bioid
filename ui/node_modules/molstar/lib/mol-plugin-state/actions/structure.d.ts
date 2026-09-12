/**
 * Copyright (c) 2018-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
import { StateAction, StateTransformer } from '../../mol-state';
import { ParamDefinition as PD } from '../../mol-util/param-definition';
import { PluginStateObject } from '../objects';
export declare const PdbDownloadProvider: {
    rcsb: PD.Group<PD.Normalize<{
        encoding: "cif" | "bcif";
    }>>;
    pdbe: PD.Group<PD.Normalize<{
        variant: "updated" | "updated-bcif" | "archival";
    }>>;
    pdbj: PD.Group<PD.Normalize<unknown>>;
};
export type PdbDownloadProvider = keyof typeof PdbDownloadProvider;
export { DownloadStructure };
type DownloadStructure = typeof DownloadStructure;
declare const DownloadStructure: StateAction<PluginStateObject.Root, void, PD.Normalize<{
    source: PD.NamedParams<PD.Normalize<{
        url: /*elided*/ any;
        format: /*elided*/ any;
        isBinary: /*elided*/ any;
        label: /*elided*/ any;
        options: /*elided*/ any;
    }>, "url"> | PD.NamedParams<PD.Normalize<{
        provider: /*elided*/ any;
        options: /*elided*/ any;
    }>, "alphafolddb"> | PD.NamedParams<PD.Normalize<{
        id: /*elided*/ any;
        options: /*elided*/ any;
    }>, "modelarchive"> | PD.NamedParams<PD.Normalize<{
        provider: /*elided*/ any;
        options: /*elided*/ any;
    }>, "pdb"> | PD.NamedParams<PD.Normalize<{
        provider: /*elided*/ any;
        options: /*elided*/ any;
    }>, "pdb-ihm"> | PD.NamedParams<PD.Normalize<{
        id: /*elided*/ any;
        options: /*elided*/ any;
    }>, "swissmodel"> | PD.NamedParams<PD.Normalize<{
        id: /*elided*/ any;
        options: /*elided*/ any;
    }>, "pubchem">;
}>>;
export declare const UpdateTrajectory: StateAction<import("../../mol-state").StateObject<any, import("../../mol-state").StateObject.Type<any>>, void, PD.Normalize<{
    action: "reset" | "advance";
    by: number | undefined;
}>>;
export declare const EnableModelCustomProps: StateAction<PluginStateObject.Molecule.Model, Promise<import("../../mol-state").StateObjectSelector<PluginStateObject.Molecule.Model, StateTransformer<import("../../mol-state").StateObject<any, import("../../mol-state").StateObject.Type<any>>, import("../../mol-state").StateObject<any, import("../../mol-state").StateObject.Type<any>>, any>>>, PD.Normalize<{
    autoAttach: string[];
    properties: PD.Normalize<{
        [x: string]: /*elided*/ any;
    }>;
}>>;
export declare const EnableStructureCustomProps: StateAction<PluginStateObject.Molecule.Structure, Promise<import("../../mol-state").StateObjectSelector<PluginStateObject.Molecule.Structure, StateTransformer<import("../../mol-state").StateObject<any, import("../../mol-state").StateObject.Type<any>>, import("../../mol-state").StateObject<any, import("../../mol-state").StateObject.Type<any>>, any>>>, PD.Normalize<{
    autoAttach: string[];
    properties: PD.Normalize<{
        [x: string]: /*elided*/ any;
    }>;
}>>;
export declare const AddTrajectory: StateAction<PluginStateObject.Root, void, PD.Normalize<{
    model: string;
    coordinates: string;
}>>;
export declare const LoadTrajectory: StateAction<PluginStateObject.Root, void, PD.Normalize<{
    source: PD.NamedParams<PD.Normalize<{
        model: /*elided*/ any;
        coordinates: /*elided*/ any;
    }>, "url"> | PD.NamedParams<PD.Normalize<{
        model: /*elided*/ any;
        coordinates: /*elided*/ any;
    }>, "file">;
}>>;
