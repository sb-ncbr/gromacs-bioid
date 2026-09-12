"use strict";
/**
 * Copyright (c) 2019-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 * @author Adam Midlik <midlik@gmail.com>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.SequenceWrapper = void 0;
const int_1 = require("../../mol-data/int");
const loci_1 = require("../../mol-model/loci");
const marker_action_1 = require("../../mol-util/marker-action");
class SequenceWrapper {
    mark(loci, action) {
        const seqIdxs = this.getSeqIndices(loci);
        if (int_1.OrderedSet.size(seqIdxs) === 0)
            return false;
        return (0, marker_action_1.applyMarkerAction)(this.markerArray, seqIdxs, action);
    }
    markResidue(loci, action) {
        if (action === 'focus')
            return this.markResidueFocus(loci, true);
        if (action === 'unfocus')
            return this.markResidueFocus(loci, false);
        if ((0, loci_1.isEveryLoci)(loci)) {
            return (0, marker_action_1.applyMarkerAction)(this.markerArray, int_1.Interval.ofLength(this.length), action);
        }
        else {
            return this.mark(loci, action);
        }
    }
    markResidueFocus(loci, focusState) {
        const value = focusState ? 1 : 0;
        if ((0, loci_1.isEveryLoci)(loci)) {
            this.focusMarkerArray.fill(value, 0, this.length);
            return true;
        }
        else {
            const seqIdxs = this.getSeqIndices(loci);
            int_1.OrderedSet.forEach(seqIdxs, seqIdx => this.focusMarkerArray[seqIdx] = value);
            return int_1.OrderedSet.size(seqIdxs) > 0;
        }
    }
    /** Return true if the position `seqIndex` in sequence view is highlighted */
    isHighlighted(seqIndex) {
        return !!(this.markerArray[seqIndex] & 1);
    }
    /** Return true if the position `seqIndex` in sequence view is selected */
    isSelected(seqIndex) {
        return !!(this.markerArray[seqIndex] & 2);
    }
    /** Return true if the position `seqIndex` in sequence view is focused */
    isFocused(seqIndex) {
        return !!(this.focusMarkerArray[seqIndex]);
    }
    constructor(data, length) {
        this.data = data;
        this.length = length;
        this.markerArray = new Uint8Array(length);
        this.focusMarkerArray = new Uint8Array(length);
    }
}
exports.SequenceWrapper = SequenceWrapper;
