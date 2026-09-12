/**
 * Copyright (c) 2019-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 * @author Adam Midlik <midlik@gmail.com>
 */
import { OrderedSet } from '../../mol-data/int';
import { Loci } from '../../mol-model/loci';
import { Structure, StructureElement, Unit } from '../../mol-model/structure';
import { Color } from '../../mol-util/color';
import { MarkerAction } from '../../mol-util/marker-action';
export type StructureUnit = {
    structure: Structure;
    units: Unit[];
};
export { SequenceWrapper };
declare abstract class SequenceWrapper<D> {
    readonly data: D;
    readonly length: number;
    abstract residueLabel(seqIdx: number): string;
    abstract residueColor(seqIdx: number): Color;
    abstract residueClass(seqIdx: number): string;
    abstract getLoci(seqIdx: number): StructureElement.Loci;
    /** Return list of sequence viewer positions that correspond to `loci` */
    abstract getSeqIndices(loci: Loci): OrderedSet;
    mark(loci: Loci, action: MarkerAction): boolean;
    markResidue(loci: Loci, action: MarkerAction | 'focus' | 'unfocus'): boolean;
    private markResidueFocus;
    /** Return true if the position `seqIndex` in sequence view is highlighted */
    isHighlighted(seqIndex: number): boolean;
    /** Return true if the position `seqIndex` in sequence view is selected */
    isSelected(seqIndex: number): boolean;
    /** Return true if the position `seqIndex` in sequence view is focused */
    isFocused(seqIndex: number): boolean;
    /** Markers for "highlighted" and "selected" (2 bits per position) */
    readonly markerArray: Uint8Array;
    /** Markers for "focused" (1 bit per position) */
    readonly focusMarkerArray: Uint8Array;
    constructor(data: D, length: number);
}
declare namespace SequenceWrapper {
    type Any = SequenceWrapper<any>;
}
