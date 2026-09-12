/**
 * Copyright (c) 2019-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 * @author Adam Midlik <midlik@gmail.com>
 */
import { OrderedSet } from '../../mol-data/int';
import { Loci } from '../../mol-model/loci';
import { StructureElement } from '../../mol-model/structure';
import { SequenceWrapper, StructureUnit } from './wrapper';
export declare class ChainSequenceWrapper extends SequenceWrapper<StructureUnit> {
    private label;
    private unitIndices;
    private loci;
    residueLabel(seqIdx: number): string;
    residueColor(seqIdx: number): import("../../mol-util/color").Color;
    residueClass(seqIdx: number): string;
    getSeqIndices(loci: Loci): OrderedSet;
    getLoci(seqIdx: number): StructureElement.Loci;
    constructor(data: StructureUnit);
}
