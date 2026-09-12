/**
 * Copyright (c) 2017-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
import { UniqueArray } from '../../mol-data/generic';
import { cantorPairing } from '../../mol-data/util';
export { InterUnitGraph };
class InterUnitGraph {
    /** Get an array of unit-pair-edges that are connected to the given unit */
    getConnectedUnits(unit) {
        if (!this.map.has(unit))
            return emptyArray;
        return this.map.get(unit);
    }
    /** Index into this.edges */
    getEdgeIndex(indexA, unitA, indexB, unitB) {
        const indices = this.edgeKeyIndex.get(InterUnitGraph.getEdgeUnitKey(unitA, unitB));
        if (indices === undefined)
            return -1;
        const index = indices.get(InterUnitGraph.getEdgeIndexKey(indexA, indexB));
        return index !== undefined ? index : -1;
    }
    /** Check if edge exists */
    hasEdge(indexA, unitA, indexB, unitB) {
        return this.getEdgeIndex(indexA, unitA, indexB, unitB) !== -1;
    }
    /** Get inter-unit edge given a pair of indices and units */
    getEdge(indexA, unitA, indexB, unitB) {
        const index = this.getEdgeIndex(indexA, unitA, indexB, unitB);
        return index !== -1 ? this.edges[index] : undefined;
    }
    /** Indices into this.edges */
    getEdgeIndices(index, unit) {
        return this.vertexKeyIndex.get(InterUnitGraph.getVertexKey(index, unit)) || [];
    }
    constructor(map) {
        this.map = map;
        let count = 0;
        const edges = [];
        const edgeKeyIndex = new Map();
        const vertexKeyIndex = new Map();
        this.map.forEach(pairEdgesArray => {
            pairEdgesArray.forEach(pairEdges => {
                count += pairEdges.edgeCount;
                pairEdges.connectedIndices.forEach(indexA => {
                    pairEdges.getEdges(indexA).forEach(edgeInfo => {
                        const { unitA, unitB } = pairEdges;
                        const edgeUnitKey = InterUnitGraph.getEdgeIndexKey(unitA, unitB);
                        const edgeIndexKey = InterUnitGraph.getEdgeIndexKey(indexA, edgeInfo.indexB);
                        const e = edgeKeyIndex.get(edgeUnitKey);
                        if (e === undefined)
                            edgeKeyIndex.set(edgeUnitKey, new Map([[edgeIndexKey, edges.length]]));
                        else
                            e.set(edgeIndexKey, edges.length);
                        const vertexKey = InterUnitGraph.getVertexKey(indexA, unitA);
                        const v = vertexKeyIndex.get(vertexKey);
                        if (v === undefined)
                            vertexKeyIndex.set(vertexKey, [edges.length]);
                        else
                            v.push(edges.length);
                        edges.push({ ...edgeInfo, indexA, unitA, unitB });
                    });
                });
            });
        });
        this.edgeCount = count;
        this.edges = edges;
        this.edgeKeyIndex = edgeKeyIndex;
        this.vertexKeyIndex = vertexKeyIndex;
    }
}
(function (InterUnitGraph) {
    class UnitPairEdges {
        hasEdges(indexA) {
            return this.edgeMap.has(indexA);
        }
        getEdges(indexA) {
            if (!this.edgeMap.has(indexA))
                return emptyArray;
            return this.edgeMap.get(indexA);
        }
        get areUnitsOrdered() {
            return this.unitA < this.unitB;
        }
        constructor(unitA, unitB, edgeCount, connectedIndices, edgeMap) {
            this.unitA = unitA;
            this.unitB = unitB;
            this.edgeCount = edgeCount;
            this.connectedIndices = connectedIndices;
            this.edgeMap = edgeMap;
        }
    }
    InterUnitGraph.UnitPairEdges = UnitPairEdges;
    function getEdgeUnitKey(unitA, unitB) {
        return cantorPairing(unitA, unitB);
    }
    InterUnitGraph.getEdgeUnitKey = getEdgeUnitKey;
    function getEdgeIndexKey(indexA, indexB) {
        return cantorPairing(indexA, indexB);
    }
    InterUnitGraph.getEdgeIndexKey = getEdgeIndexKey;
    function getVertexKey(index, unit) {
        return cantorPairing(index, unit);
    }
    InterUnitGraph.getVertexKey = getVertexKey;
    //
    function addMapEntry(map, a, b) {
        if (map.has(a))
            map.get(a).push(b);
        else
            map.set(a, [b]);
    }
    class Builder {
        constructor() {
            this.map = new Map();
        }
        startUnitPair(unitA, unitB) {
            this.uA = unitA;
            this.uB = unitB;
            this.mapAB = new Map();
            this.mapBA = new Map();
            this.linkedA = UniqueArray.create();
            this.linkedB = UniqueArray.create();
            this.linkCount = 0;
        }
        finishUnitPair() {
            if (this.linkCount === 0)
                return;
            addMapEntry(this.map, this.uA, new UnitPairEdges(this.uA, this.uB, this.linkCount, this.linkedA.array, this.mapAB));
            addMapEntry(this.map, this.uB, new UnitPairEdges(this.uB, this.uA, this.linkCount, this.linkedB.array, this.mapBA));
        }
        add(indexA, indexB, props) {
            addMapEntry(this.mapAB, indexA, { indexB, props });
            addMapEntry(this.mapBA, indexB, { indexB: indexA, props });
            UniqueArray.add(this.linkedA, indexA, indexA);
            UniqueArray.add(this.linkedB, indexB, indexB);
            this.linkCount += 1;
        }
        getMap() {
            return this.map;
        }
    }
    InterUnitGraph.Builder = Builder;
})(InterUnitGraph || (InterUnitGraph = {}));
const emptyArray = [];
