/**
 * Copyright (c) 2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 */
import { InteractionsProps } from '../../mol-model-props/computed/interactions';
import { StructureElement } from '../../mol-model/structure';
import { RuntimeContext } from '../../mol-task';
import { StructureInteractions } from './model';
export interface ComputeInteractionsOptions {
    interactions?: InteractionsProps;
}
export declare function computeContacts(ctx: RuntimeContext, selection: readonly {
    structureRef: string;
    loci: StructureElement.Loci;
}[], options?: ComputeInteractionsOptions): Promise<StructureInteractions>;
