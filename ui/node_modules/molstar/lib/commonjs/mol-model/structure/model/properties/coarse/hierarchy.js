"use strict";
/**
 * Copyright (c) 2018-2022 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.CoarseHierarchy = void 0;
exports.CoarseElementReference = CoarseElementReference;
exports.CoarseElementKey = CoarseElementKey;
const db_1 = require("../../../../../mol-data/db");
const int_1 = require("../../../../../mol-data/int");
const sorted_ranges_1 = require("../../../../../mol-data/int/sorted-ranges");
const coarse_index_1 = require("../utils/coarse-index");
const EmptyCoarseElements = {
    chainKey: [],
    entityKey: [],
    findSequenceKey: () => -1,
    findChainKey: () => -1,
    getEntityFromChain: () => -1,
    count: 0,
    entity_id: db_1.Column.Undefined(0, db_1.Column.Schema.str),
    asym_id: db_1.Column.Undefined(0, db_1.Column.Schema.str),
    seq_id_begin: db_1.Column.Undefined(0, db_1.Column.Schema.int),
    seq_id_end: db_1.Column.Undefined(0, db_1.Column.Schema.int),
    chainElementSegments: int_1.Segmentation.create([]),
    polymerRanges: sorted_ranges_1.SortedRanges.ofSortedRanges([]),
    gapRanges: sorted_ranges_1.SortedRanges.ofSortedRanges([]),
};
function CoarseElementReference() { return { kind: undefined, index: -1 }; }
function CoarseElementKey() { return { label_entity_id: '', label_asym_id: '', label_seq_id: -1 }; }
var CoarseHierarchy;
(function (CoarseHierarchy) {
    CoarseHierarchy.Empty = {
        isDefined: false,
        spheres: EmptyCoarseElements,
        gaussians: EmptyCoarseElements,
        index: coarse_index_1.EmptyCoarseIndex,
    };
})(CoarseHierarchy || (exports.CoarseHierarchy = CoarseHierarchy = {}));
