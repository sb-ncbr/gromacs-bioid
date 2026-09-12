"use strict";
/**
 * Copyright (c) 2019-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 * @author Adam Midlik <midlik@gmail.com>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.ChainSequenceWrapper = void 0;
const int_1 = require("../../mol-data/int");
const structure_1 = require("../../mol-model/structure");
const names_1 = require("../../mol-util/color/names");
const wrapper_1 = require("./wrapper");
class ChainSequenceWrapper extends wrapper_1.SequenceWrapper {
    residueLabel(seqIdx) {
        return this.label;
    }
    residueColor(seqIdx) {
        return names_1.ColorNames.black;
    }
    residueClass(seqIdx) {
        return 'msp-sequence-present';
    }
    getSeqIndices(loci) {
        const { structure } = this.data;
        if (structure_1.StructureElement.Loci.is(loci)) {
            if (!structure_1.Structure.areRootsEquivalent(loci.structure, structure))
                return int_1.Interval.Empty;
            loci = structure_1.StructureElement.Loci.remap(loci, structure);
            for (const e of loci.elements) {
                const indices = this.unitIndices.get(e.unit.id);
                if (indices) {
                    if (int_1.OrderedSet.isSubset(indices, e.indices)) {
                        return int_1.Interval.ofSingleton(0);
                    }
                }
            }
        }
        else if (structure_1.Structure.isLoci(loci)) {
            if (!structure_1.Structure.areRootsEquivalent(loci.structure, structure))
                return int_1.Interval.Empty;
            return int_1.Interval.ofSingleton(0);
        }
        return int_1.Interval.Empty;
    }
    getLoci(seqIdx) {
        return this.loci;
    }
    constructor(data) {
        let residueCount = 0;
        let elementCount = 0;
        const counts = [];
        const l = structure_1.StructureElement.Location.create(data.structure);
        const unitIndices = new Map();
        const lociElements = [];
        for (let i = 0, il = data.units.length; i < il; ++i) {
            const unit = data.units[i];
            structure_1.StructureElement.Location.set(l, data.structure, unit, unit.elements[0]);
            const entitySeq = unit.model.sequence.byEntityKey[structure_1.StructureProperties.entity.key(l)];
            if (entitySeq)
                residueCount += entitySeq.sequence.length;
            elementCount += unit.elements.length;
            const indices = int_1.Interval.ofBounds(0, unit.elements.length);
            unitIndices.set(unit.id, indices);
            lociElements.push({ unit, indices });
        }
        if (residueCount > 0)
            counts.push(`${residueCount} residues`);
        counts.push(`${elementCount} elements`);
        const length = 1;
        super(data, length);
        this.label = `Whole Chain (${counts.join(', ')})`;
        this.unitIndices = unitIndices;
        this.loci = structure_1.StructureElement.Loci(this.data.structure, lociElements);
    }
}
exports.ChainSequenceWrapper = ChainSequenceWrapper;
