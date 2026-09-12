/**
 * Copyright (c) 2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
import { ElementIndex } from '../model/indexing';
import { Structure } from './structure';
import { Unit } from './unit';
/** Serial index of an element in the structure across all units */
export type SerialIndex = {
    readonly '@type': 'serial-index';
} & number;
export interface SerialMapping {
    /** Cumulative count of preceding elements for each unit */
    cumulativeUnitElementCount: ArrayLike<number>;
    /** Unit index for each serial element in the structure */
    unitIndices: ArrayLike<number>;
    /** Element index for each serial element in the structure */
    elementIndices: ArrayLike<ElementIndex>;
    /** Get serial index of element in the structure */
    getSerialIndex: (unit: Unit, element: ElementIndex) => SerialIndex;
}
export declare function getSerialMapping(structure: Structure): SerialMapping;
export interface IntraUnitBondMapping {
    bondCount: number;
    unitIndex: ArrayLike<number>;
    unitEdgeIndex: ArrayLike<number>;
    unitGroupIndex: ArrayLike<number>;
    unitGroupOffset: ArrayLike<number>;
}
export declare function getIntraUnitBondMapping(structure: Structure): IntraUnitBondMapping;
