/**
 * Copyright (c) 2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 */
export function getCoarseIndex(data) {
    return new Index(data);
}
class EmptyIndex {
    findElement(key, out) {
        out.kind = undefined;
        out.index = -1;
        return false;
    }
    findSphereElement(key) {
        return -1;
    }
    findGaussianElement(key) {
        return -1;
    }
}
export const EmptyCoarseIndex = new EmptyIndex();
class Index {
    get sphereMapping() {
        if (!this._sphereMapping)
            this._sphereMapping = buildMapping(this.data.spheres);
        return this._sphereMapping;
    }
    get gaussianMapping() {
        if (!this._gaussianMapping)
            this._gaussianMapping = buildMapping(this.data.gaussians);
        return this._gaussianMapping;
    }
    findSphereElement(key) {
        var _a;
        const mapping = this.sphereMapping;
        let xs = mapping[key.label_entity_id];
        if (!xs)
            return -1;
        xs = xs[key.label_asym_id];
        if (!xs)
            return -1;
        return (_a = xs[key.label_seq_id]) !== null && _a !== void 0 ? _a : -1;
    }
    findGaussianElement(key) {
        var _a;
        const mapping = this.gaussianMapping;
        let xs = mapping[key.label_entity_id];
        if (!xs)
            return -1;
        xs = xs[key.label_asym_id];
        if (!xs)
            return -1;
        return (_a = xs[key.label_seq_id]) !== null && _a !== void 0 ? _a : -1;
    }
    findElement(key, out) {
        const sphere = this.findSphereElement(key);
        if (sphere >= 0) {
            out.kind = 'spheres';
            out.index = sphere;
            return true;
        }
        const gaussian = this.findGaussianElement(key);
        if (gaussian >= 0) {
            out.kind = 'gaussians';
            out.index = gaussian;
            return true;
        }
        return false;
    }
    constructor(data) {
        this.data = data;
        this._sphereMapping = void 0;
        this._gaussianMapping = void 0;
    }
}
function buildMapping({ count, entity_id, asym_id, seq_id_begin, seq_id_end }) {
    const ret = {};
    for (let i = 0; i < count; i++) {
        const entityId = entity_id.value(i);
        const asymId = asym_id.value(i);
        if (!ret[entityId])
            ret[entityId] = {};
        if (!ret[entityId][asymId])
            ret[entityId][asymId] = {};
        const elements = ret[entityId][asymId];
        const seqIdBegin = seq_id_begin.value(i);
        const seqIdEnd = seq_id_end.value(i);
        for (let seqId = seqIdBegin; seqId <= seqIdEnd; seqId++) {
            elements[seqId] = i;
        }
    }
    return ret;
}
