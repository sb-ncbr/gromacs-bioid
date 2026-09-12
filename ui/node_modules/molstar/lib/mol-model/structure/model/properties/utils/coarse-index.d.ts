/**
 * Copyright (c) 2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 */
import { CoarseElementData, CoarseIndex } from '../coarse';
export declare function getCoarseIndex(data: {
    spheres: CoarseElementData;
    gaussians: CoarseElementData;
}): CoarseIndex;
export declare const EmptyCoarseIndex: CoarseIndex;
