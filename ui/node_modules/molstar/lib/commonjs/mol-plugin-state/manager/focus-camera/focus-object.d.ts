/**
 * Copyright (c) 2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Adam Midlik <midlik@gmail.com>
 */
import { Camera } from '../../../mol-canvas3d/camera';
import { Sphere3D } from '../../../mol-math/geometry';
import { PluginContext } from '../../../mol-plugin/context';
import { PluginState } from '../../../mol-plugin/state';
import { StateTransform } from '../../../mol-state';
/** Return camera snapshot focused on a plugin state object cell (if `targetRef` is defined)
 * or on the whole scene (if `targetRef` is undefined).
 * If `direction` and `up` are not provided, use current camera orientation. */
export declare function getFocusSnapshot(plugin: PluginContext, options: PluginState.SnapshotFocusInfo & {
    minRadius?: number;
}): Partial<Camera.Snapshot> | undefined;
/** Return the bounding sphere of a plugin state object cell */
export declare function getCellBoundingSphere(plugin: PluginContext, cellRef: StateTransform.Ref): Sphere3D | undefined;
/** Return the bounding sphere of the whole visible scene. */
export declare function getPluginBoundingSphere(plugin: PluginContext): Sphere3D;
