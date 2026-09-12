/**
 * Copyright (c) 2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 */
import { Structure } from '../../mol-model/structure';
import { InteractionElementSchema, StructureInteractions } from './model';
export declare function getCustomInteractionData(interactions: InteractionElementSchema[], structures: {
    [ref: string]: Structure;
}): StructureInteractions;
