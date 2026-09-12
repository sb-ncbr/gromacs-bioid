"use strict";
/**
 * Copyright (c) 2018-2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.VolumeRepresentationRegistry = void 0;
const representation_1 = require("../representation");
const isosurface_1 = require("./isosurface");
const object_1 = require("../../mol-util/object");
const slice_1 = require("./slice");
const direct_volume_1 = require("./direct-volume");
const segment_1 = require("./segment");
const dot_1 = require("./dot");
class VolumeRepresentationRegistry extends representation_1.RepresentationRegistry {
    constructor() {
        super();
        (0, object_1.objectForEach)(VolumeRepresentationRegistry.BuiltIn, (p, k) => {
            if (p.name !== k)
                throw new Error(`Fix BuiltInVolumeRepresentations to have matching names. ${p.name} ${k}`);
            this.add(p);
        });
    }
}
exports.VolumeRepresentationRegistry = VolumeRepresentationRegistry;
(function (VolumeRepresentationRegistry) {
    VolumeRepresentationRegistry.BuiltIn = {
        'direct-volume': direct_volume_1.DirectVolumeRepresentationProvider,
        'dot': dot_1.DotRepresentationProvider,
        'isosurface': isosurface_1.IsosurfaceRepresentationProvider,
        'segment': segment_1.SegmentRepresentationProvider,
        'slice': slice_1.SliceRepresentationProvider,
    };
})(VolumeRepresentationRegistry || (exports.VolumeRepresentationRegistry = VolumeRepresentationRegistry = {}));
