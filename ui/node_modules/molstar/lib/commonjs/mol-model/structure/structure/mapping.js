"use strict";
/**
 * Copyright (c) 2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.getSerialMapping = getSerialMapping;
exports.getIntraUnitBondMapping = getIntraUnitBondMapping;
const ordered_set_1 = require("../../../mol-data/int/ordered-set");
const unit_1 = require("./unit");
function getSerialMapping(structure) {
    const { units, elementCount, unitIndexMap } = structure;
    const cumulativeUnitElementCount = new Uint32Array(units.length);
    const unitIndices = new Uint32Array(elementCount);
    const elementIndices = new Uint32Array(elementCount);
    for (let i = 0, m = 0, il = units.length; i < il; ++i) {
        cumulativeUnitElementCount[i] = m;
        const { elements } = units[i];
        for (let j = 0, jl = elements.length; j < jl; ++j) {
            const mj = m + j;
            unitIndices[mj] = i;
            elementIndices[mj] = elements[j];
        }
        m += elements.length;
    }
    return {
        cumulativeUnitElementCount,
        unitIndices,
        elementIndices,
        getSerialIndex: (unit, element) => cumulativeUnitElementCount[unitIndexMap.get(unit.id)] + ordered_set_1.OrderedSet.indexOf(unit.elements, element)
    };
}
function getIntraUnitBondMapping(structure) {
    let bondCount = 0;
    const unitGroupOffset = [];
    for (const ug of structure.unitSymmetryGroups) {
        unitGroupOffset.push(bondCount);
        const unit = ug.units[0];
        if (unit_1.Unit.isAtomic(unit)) {
            bondCount += unit.bonds.edgeCount * 2 * ug.units.length;
        }
    }
    const unitIndex = new Uint32Array(bondCount);
    const unitEdgeIndex = new Uint32Array(bondCount);
    const unitGroupIndex = new Uint32Array(bondCount);
    let idx = 0;
    let unitIdx = 0;
    for (const ug of structure.unitSymmetryGroups) {
        const unit = ug.units[0];
        if (unit_1.Unit.isAtomic(unit)) {
            const edgeCount = unit.bonds.edgeCount * 2;
            for (let i = 0, il = ug.units.length; i < il; ++i) {
                for (let j = 0, jl = edgeCount; j < jl; ++j) {
                    unitIndex[idx] = unitIdx;
                    unitEdgeIndex[idx] = j;
                    unitGroupIndex[idx] = i;
                    idx += 1;
                }
            }
        }
        unitIdx += 1;
    }
    return { bondCount, unitIndex, unitEdgeIndex, unitGroupIndex, unitGroupOffset };
}
