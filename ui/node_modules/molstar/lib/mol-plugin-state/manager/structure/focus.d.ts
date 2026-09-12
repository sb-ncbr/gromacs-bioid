/**
 * Copyright (c) 2020-2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 * @author David Sehnal <david.sehnal@gmail.com>
 * @author Adam Midlik <midlik@gmail.com>
 */
import { Loci } from '../../../mol-model/loci';
import { StructureElement } from '../../../mol-model/structure';
import { PluginContext } from '../../../mol-plugin/context';
import { StatefulPluginComponent } from '../../component';
export type FocusEntry = {
    label: string;
    loci: StructureElement.Loci;
    category?: string;
};
export interface StructureFocusSnapshot {
    current?: {
        label: string;
        ref: string;
        bundle: StructureElement.Bundle;
        category?: string;
    };
}
interface StructureFocusManagerState {
    current?: FocusEntry;
    history: FocusEntry[];
}
export declare class StructureFocusManager extends StatefulPluginComponent<StructureFocusManagerState> {
    private plugin;
    readonly events: {
        historyUpdated: import("rxjs").Subject<undefined>;
    };
    readonly behaviors: {
        current: import("rxjs").BehaviorSubject<FocusEntry | undefined>;
    };
    get current(): FocusEntry | undefined;
    get history(): FocusEntry[];
    /** Last added or removed loci */
    private referenceLoci;
    private tryAddHistory;
    set(entry: FocusEntry): void;
    tryGetRange(loci: Loci): StructureElement.Loci | undefined;
    setFromLoci(anyLoci: Loci): void;
    addFromLoci(anyLoci: Loci): void;
    toggleFromLoci(anyLoci: Loci): void;
    extendFromLoci(anyLoci: Loci): void;
    clear(): void;
    getSnapshot(): StructureFocusSnapshot;
    setSnapshot(snapshot: StructureFocusSnapshot): void;
    constructor(plugin: PluginContext);
}
export {};
