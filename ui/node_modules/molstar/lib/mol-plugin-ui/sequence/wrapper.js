/**
 * Copyright (c) 2019-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 * @author Adam Midlik <midlik@gmail.com>
 */
import { Interval, OrderedSet } from '../../mol-data/int';
import { isEveryLoci } from '../../mol-model/loci';
import { applyMarkerAction } from '../../mol-util/marker-action';
export { SequenceWrapper };
class SequenceWrapper {
    mark(loci, action) {
        const seqIdxs = this.getSeqIndices(loci);
        if (OrderedSet.size(seqIdxs) === 0)
            return false;
        return applyMarkerAction(this.markerArray, seqIdxs, action);
    }
    markResidue(loci, action) {
        if (action === 'focus')
            return this.markResidueFocus(loci, true);
        if (action === 'unfocus')
            return this.markResidueFocus(loci, false);
        if (isEveryLoci(loci)) {
            return applyMarkerAction(this.markerArray, Interval.ofLength(this.length), action);
        }
        else {
            return this.mark(loci, action);
        }
    }
    markResidueFocus(loci, focusState) {
        const value = focusState ? 1 : 0;
        if (isEveryLoci(loci)) {
            this.focusMarkerArray.fill(value, 0, this.length);
            return true;
        }
        else {
            const seqIdxs = this.getSeqIndices(loci);
            OrderedSet.forEach(seqIdxs, seqIdx => this.focusMarkerArray[seqIdx] = value);
            return OrderedSet.size(seqIdxs) > 0;
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
