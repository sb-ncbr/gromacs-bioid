/**
 * Copyright (c) 2018-2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
import { RepresentationRegistry } from '../representation';
import { IsosurfaceRepresentationProvider } from './isosurface';
import { objectForEach } from '../../mol-util/object';
import { SliceRepresentationProvider } from './slice';
import { DirectVolumeRepresentationProvider } from './direct-volume';
import { SegmentRepresentationProvider } from './segment';
import { DotRepresentationProvider } from './dot';
export class VolumeRepresentationRegistry extends RepresentationRegistry {
    constructor() {
        super();
        objectForEach(VolumeRepresentationRegistry.BuiltIn, (p, k) => {
            if (p.name !== k)
                throw new Error(`Fix BuiltInVolumeRepresentations to have matching names. ${p.name} ${k}`);
            this.add(p);
        });
    }
}
(function (VolumeRepresentationRegistry) {
    VolumeRepresentationRegistry.BuiltIn = {
        'direct-volume': DirectVolumeRepresentationProvider,
        'dot': DotRepresentationProvider,
        'isosurface': IsosurfaceRepresentationProvider,
        'segment': SegmentRepresentationProvider,
        'slice': SliceRepresentationProvider,
    };
})(VolumeRepresentationRegistry || (VolumeRepresentationRegistry = {}));
