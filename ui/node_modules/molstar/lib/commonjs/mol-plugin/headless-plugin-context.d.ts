/**
 * Copyright (c) 2023-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Adam Midlik <midlik@gmail.com>
 */
import { type BufferRet as JpegBufferRet } from 'jpeg-js';
import { type PNG } from 'pngjs';
import { PostprocessingProps } from '../mol-canvas3d/passes/postprocessing';
import { PluginContext } from './context';
import { PluginSpec } from './spec';
import { ExternalModules, HeadlessScreenshotHelper, HeadlessScreenshotHelperOptions, RawImageData } from './util/headless-screenshot';
/** PluginContext that can be used in Node.js (without DOM) */
export declare class HeadlessPluginContext extends PluginContext {
    renderer: HeadlessScreenshotHelper;
    /** External modules (`gl` and optionally `pngjs` and `jpeg-js`) must be provided to the constructor (this is to avoid Mol* being dependent on these packages which are only used here) */
    constructor(externalModules: ExternalModules, spec: PluginSpec, canvasSize?: {
        width: number;
        height: number;
    }, rendererOptions?: HeadlessScreenshotHelperOptions);
    /** Render the current plugin state and save to a PNG or JPEG file */
    saveImage(outPath: string, imageSize?: {
        width: number;
        height: number;
    }, props?: Partial<PostprocessingProps>, format?: 'png' | 'jpeg', jpegQuality?: number): Promise<void>;
    /** Render the current plugin state and return as raw image data */
    getImageRaw(imageSize?: {
        width: number;
        height: number;
    }, props?: Partial<PostprocessingProps>): Promise<RawImageData>;
    /** Render the current plugin state and return as a PNG object */
    getImagePng(imageSize?: {
        width: number;
        height: number;
    }, props?: Partial<PostprocessingProps>): Promise<PNG>;
    /** Render the current plugin state and return as a JPEG object */
    getImageJpeg(imageSize?: {
        width: number;
        height: number;
    }, props?: Partial<PostprocessingProps>, jpegQuality?: number): Promise<JpegBufferRet>;
    /** Get the current plugin state */
    getStateSnapshot(): Promise<import("../mol-plugin-state/manager/snapshots").PluginStateSnapshotManager.StateSnapshot>;
    /** Save the current plugin state to a MOLJ file */
    saveStateSnapshot(outPath: string): Promise<void>;
    /** Render plugin state snapshots animation and return as raw MP4 data */
    getAnimation(options?: {
        quantization?: number;
        size?: {
            width: number;
            height: number;
        };
        fps?: number;
        postprocessing?: Partial<PostprocessingProps>;
    }): Promise<Uint8Array<ArrayBufferLike>>;
    /** Render plugin state snapshots animation and save to a MP4 file */
    saveAnimation(outPath: string, options?: {
        quantization?: number;
        size?: {
            width: number;
            height: number;
        };
        fps?: number;
        postprocessing?: Partial<PostprocessingProps>;
    }): Promise<void>;
}
