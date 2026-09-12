/**
 * Copyright (c) 2018-2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 * @author Ventura Rivera <venturaxrivera@gmail.com>
 */
import { CreateVolumeStreamingBehavior } from '../mol-plugin/behavior/dynamic/volume-streaming/transformers';
import { DefaultPluginSpec } from '../mol-plugin/spec';
import { VolumeStreamingCustomControls } from './custom/volume';
export const DefaultPluginUISpec = () => ({
    ...DefaultPluginSpec(),
    customParamEditors: [
        [CreateVolumeStreamingBehavior, VolumeStreamingCustomControls]
    ],
});
