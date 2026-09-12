/**
 * Copyright (c) 2018-2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
/** A null value Location */
export const NullLocation = { kind: 'null-location' };
export function isNullLocation(x) {
    return !!x && x.kind === 'null-location';
}
export function DataLocation(tag, data, element) {
    return { kind: 'data-location', tag, data, element };
}
export function isDataLocation(x) {
    return !!x && x.kind === 'data-location';
}
/**
 * A direct Location.
 *
 * For it, the location is implicitly clear from context and is not explicitly given.
 * This is used for themes with direct-volume rendering where the location is the volume
 * grid cell itself and coloring is applied in a shader on the GPU.
 */
export const DirectLocation = { kind: 'direct-location' };
export function isDirectLocation(x) {
    return !!x && x.kind === 'direct-location';
}
