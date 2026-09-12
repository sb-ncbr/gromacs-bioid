"use strict";
/**
 * Copyright (c) 2019-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 * @author Adam Midlik <midlik@gmail.com>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.ElementSequenceWrapper = void 0;
const int_1 = require("../../mol-data/int");
const structure_1 = require("../../mol-model/structure");
const names_1 = require("../../mol-util/color/names");
const wrapper_1 = require("./wrapper");
class ElementSequenceWrapper extends wrapper_1.SequenceWrapper {
    residueLabel(seqIdx) {
        return 'X';
    }
    residueColor(seqIdx) {
        return names_1.ColorNames.black;
    }
    residueClass(seqIdx) {
        return 'msp-sequence-present';
    }
    getSeqIndices(loci) {
        const { structure, units } = this.data;
        if (structure_1.StructureElement.Loci.is(loci)) {
            if (!structure_1.Structure.areRootsEquivalent(loci.structure, structure))
                return int_1.Interval.Empty;
            loci = structure_1.StructureElement.Loci.remap(loci, structure);
            for (const e of loci.elements) {
                const indices = this.unitIndices.get(e.unit.id);
                if (indices) {
                    if (int_1.OrderedSet.isSubset(indices, e.indices)) {
                        // this assumes this SequnceWrapper has only a single unit, otherwise we'd need to collect indices from all units and apply offsets
                        return e.indices;
                    }
                }
            }
        }
        else if (structure_1.Structure.isLoci(loci)) {
            if (!structure_1.Structure.areRootsEquivalent(loci.structure, structure))
                return int_1.Interval.Empty;
            for (let i = 0, il = units.length; i < il; ++i) {
                const indices = this.unitIndices.get(units[i].id);
                return indices;
            }
        }
        return int_1.Interval.Empty;
    }
    getLoci(seqIdx) {
        const { units } = this.data;
        const lociElements = [];
        let offset = 0;
        for (let i = 0, il = units.length; i < il; ++i) {
            const unit = units[i];
            if (seqIdx < offset + unit.elements.length) {
                lociElements.push({ unit, indices: int_1.Interval.ofSingleton(seqIdx - offset) });
                break;
            }
            offset += unit.elements.length;
        }
        return structure_1.StructureElement.Loci(this.data.structure, lociElements);
    }
    constructor(data) {
        let length = 0;
        const unitIndices = new Map();
        const lociElements = [];
        for (let i = 0, il = data.units.length; i < il; ++i) {
            const unit = data.units[i];
            length += unit.elements.length;
            const indices = int_1.Interval.ofBounds(0, unit.elements.length);
            unitIndices.set(unit.id, indices);
            lociElements.push({ unit, indices });
        }
        super(data, length);
        this.unitIndices = unitIndices;
    }
}
exports.ElementSequenceWrapper = ElementSequenceWrapper;
