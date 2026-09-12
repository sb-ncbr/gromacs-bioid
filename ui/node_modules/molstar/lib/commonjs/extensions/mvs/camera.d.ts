/**
 * Copyright (c) 2023-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Adam Midlik <midlik@gmail.com>
 * @author David Sehnal <david.sehnal@gmail.com>
 */
import { Camera } from '../../mol-canvas3d/camera';
import { Canvas3DProps } from '../../mol-canvas3d/canvas3d';
import { PluginContext } from '../../mol-plugin/context';
import { PluginState } from '../../mol-plugin/state';
import { StateObjectSelector } from '../../mol-state';
import { MolstarLoadingContext } from './load';
import { SnapshotMetadata } from './mvs-data';
import { MolstarNodeParams } from './tree/molstar/molstar-tree';
/** Set the camera position to the current position (thus suppress automatic adjustment). */
export declare function suppressCameraAutoreset(plugin: PluginContext): Promise<void>;
/** Set the camera based on a camera node params. */
export declare function setCamera(plugin: PluginContext, params: MolstarNodeParams<'camera'>): Promise<void>;
export declare function cameraParamsToCameraSnapshot(plugin: PluginContext, params: MolstarNodeParams<'camera'>): Partial<Camera.Snapshot>;
/** Focus the camera on the bounding sphere of a (sub)structure (or on the whole scene if `structureNodeSelector` is undefined).
  * Orient the camera based on a focus node params. **/
export declare function setFocus(plugin: PluginContext, focuses: {
    target: StateObjectSelector;
    params: MolstarNodeParams<'focus'>;
}[]): Promise<void>;
/** Create object for PluginState.Snapshot.camera based on tree loading context and MVS snapshot metadata */
export declare function createPluginStateSnapshotCamera(plugin: PluginContext, context: MolstarLoadingContext, metadata: SnapshotMetadata & {
    previousTransitionDurationMs?: number;
}): PluginState.Snapshot['camera'];
/** Set canvas properties based on a canvas node params. */
export declare function setCanvas(plugin: PluginContext, params: MolstarNodeParams<'canvas'> | undefined): void;
/** Create a deep copy of `oldCanvasProps` with values modified according to a canvas node params. */
export declare function modifyCanvasProps(oldCanvasProps: Canvas3DProps, params: MolstarNodeParams<'canvas'> | undefined): Canvas3DProps;
