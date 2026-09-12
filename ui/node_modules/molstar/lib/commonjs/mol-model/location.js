"use strict";
/**
 * Copyright (c) 2018-2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.DirectLocation = exports.NullLocation = void 0;
exports.isNullLocation = isNullLocation;
exports.DataLocation = DataLocation;
exports.isDataLocation = isDataLocation;
exports.isDirectLocation = isDirectLocation;
/** A null value Location */
exports.NullLocation = { kind: 'null-location' };
function isNullLocation(x) {
    return !!x && x.kind === 'null-location';
}
function DataLocation(tag, data, element) {
    return { kind: 'data-location', tag, data, element };
}
function isDataLocation(x) {
    return !!x && x.kind === 'data-location';
}
/**
 * A direct Location.
 *
 * For it, the location is implicitly clear from context and is not explicitly given.
 * This is used for themes with direct-volume rendering where the location is the volume
 * grid cell itself and coloring is applied in a shader on the GPU.
 */
exports.DirectLocation = { kind: 'direct-location' };
function isDirectLocation(x) {
    return !!x && x.kind === 'direct-location';
}
