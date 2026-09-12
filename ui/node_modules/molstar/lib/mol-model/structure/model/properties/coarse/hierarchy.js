/**
 * Copyright (c) 2018-2022 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
import { Column } from '../../../../../mol-data/db';
import { Segmentation } from '../../../../../mol-data/int';
import { SortedRanges } from '../../../../../mol-data/int/sorted-ranges';
import { EmptyCoarseIndex } from '../utils/coarse-index';
const EmptyCoarseElements = {
    chainKey: [],
    entityKey: [],
    findSequenceKey: () => -1,
    findChainKey: () => -1,
    getEntityFromChain: () => -1,
    count: 0,
    entity_id: Column.Undefined(0, Column.Schema.str),
    asym_id: Column.Undefined(0, Column.Schema.str),
    seq_id_begin: Column.Undefined(0, Column.Schema.int),
    seq_id_end: Column.Undefined(0, Column.Schema.int),
    chainElementSegments: Segmentation.create([]),
    polymerRanges: SortedRanges.ofSortedRanges([]),
    gapRanges: SortedRanges.ofSortedRanges([]),
};
export function CoarseElementReference() { return { kind: undefined, index: -1 }; }
export function CoarseElementKey() { return { label_entity_id: '', label_asym_id: '', label_seq_id: -1 }; }
export var CoarseHierarchy;
(function (CoarseHierarchy) {
    CoarseHierarchy.Empty = {
        isDefined: false,
        spheres: EmptyCoarseElements,
        gaussians: EmptyCoarseElements,
        index: EmptyCoarseIndex,
    };
})(CoarseHierarchy || (CoarseHierarchy = {}));
