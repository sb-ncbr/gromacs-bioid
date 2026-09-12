/**
 * Copyright (c) 2018-2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
import { StructureElement } from './structure';
import { Bond } from './structure/structure/unit/bonds';
import { ShapeGroup } from './shape/shape';
import { PositionLocation } from '../mol-geo/util/location-iterator';
import { Volume } from './volume';
/** A null value Location */
export declare const NullLocation: {
    kind: "null-location";
};
export type NullLocation = typeof NullLocation;
export declare function isNullLocation(x: any): x is NullLocation;
/** A generic data Location */
export interface DataLocation<T = unknown, E = unknown> {
    readonly kind: 'data-location';
    readonly tag: string;
    readonly data: T;
    element: E;
}
export declare function DataLocation<T = unknown, E = unknown>(tag: string, data: T, element: E): DataLocation<T, E>;
export declare function isDataLocation(x: any): x is DataLocation;
/**
 * A direct Location.
 *
 * For it, the location is implicitly clear from context and is not explicitly given.
 * This is used for themes with direct-volume rendering where the location is the volume
 * grid cell itself and coloring is applied in a shader on the GPU.
 */
export declare const DirectLocation: {
    kind: "direct-location";
};
export type DirectLocation = typeof DirectLocation;
export declare function isDirectLocation(x: any): x is DirectLocation;
export type Location = StructureElement.Location | Bond.Location | ShapeGroup.Location | PositionLocation | DataLocation | NullLocation | DirectLocation | Volume.Cell.Location | Volume.Segment.Location;
