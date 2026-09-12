/**
 * Copyright (c) 2023-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Adam Midlik <midlik@gmail.com>
 */
import fs from 'fs';
import { Mp4Export } from '../extensions/mp4-export';
import { encodeMp4Animation } from '../extensions/mp4-export/encoder';
import { AnimateStateSnapshots } from '../mol-plugin-state/animation/built-in/state-snapshots';
import { Task } from '../mol-task';
import { PluginContext } from './context';
import { HeadlessScreenshotHelper } from './util/headless-screenshot';
/** PluginContext that can be used in Node.js (without DOM) */
export class HeadlessPluginContext extends PluginContext {
    /** External modules (`gl` and optionally `pngjs` and `jpeg-js`) must be provided to the constructor (this is to avoid Mol* being dependent on these packages which are only used here) */
    constructor(externalModules, spec, canvasSize = { width: 640, height: 480 }, rendererOptions) {
        super(spec);
        this.renderer = new HeadlessScreenshotHelper(externalModules, canvasSize, undefined, rendererOptions);
        this.canvas3d = this.renderer.canvas3d;
    }
    /** Render the current plugin state and save to a PNG or JPEG file */
    async saveImage(outPath, imageSize, props, format, jpegQuality = 90) {
        const task = Task.create('Render Screenshot', async (ctx) => {
            this.canvas3d.commit(true);
            return await this.renderer.saveImage(ctx, outPath, imageSize, props, format, jpegQuality);
        });
        return this.runTask(task);
    }
    /** Render the current plugin state and return as raw image data */
    async getImageRaw(imageSize, props) {
        const task = Task.create('Render Screenshot', async (ctx) => {
            this.canvas3d.commit(true);
            return await this.renderer.getImageRaw(ctx, imageSize, props);
        });
        return this.runTask(task);
    }
    /** Render the current plugin state and return as a PNG object */
    async getImagePng(imageSize, props) {
        const task = Task.create('Render Screenshot', async (ctx) => {
            this.canvas3d.commit(true);
            return await this.renderer.getImagePng(ctx, imageSize, props);
        });
        return this.runTask(task);
    }
    /** Render the current plugin state and return as a JPEG object */
    async getImageJpeg(imageSize, props, jpegQuality = 90) {
        const task = Task.create('Render Screenshot', async (ctx) => {
            this.canvas3d.commit(true);
            return await this.renderer.getImageJpeg(ctx, imageSize, props);
        });
        return this.runTask(task);
    }
    /** Get the current plugin state */
    async getStateSnapshot() {
        this.canvas3d.commit(true);
        return await this.managers.snapshot.getStateSnapshot({ params: {} });
    }
    /** Save the current plugin state to a MOLJ file */
    async saveStateSnapshot(outPath) {
        const snapshot = await this.getStateSnapshot();
        const snapshot_json = JSON.stringify(snapshot, null, 2);
        await new Promise(resolve => {
            fs.writeFile(outPath, snapshot_json, () => resolve());
        });
    }
    /** Render plugin state snapshots animation and return as raw MP4 data */
    async getAnimation(options) {
        if (!this.state.hasBehavior(Mp4Export)) {
            throw new Error('PluginContext must have Mp4Export extension registered in order to save animation.');
        }
        const task = Task.create('Export Animation', async (ctx) => {
            var _a, _b;
            const { width, height } = (_a = options === null || options === void 0 ? void 0 : options.size) !== null && _a !== void 0 ? _a : this.renderer.canvasSize;
            const movie = await encodeMp4Animation(this, ctx, {
                animation: { definition: AnimateStateSnapshots, params: {} },
                width,
                height,
                viewport: { x: 0, y: 0, width, height },
                quantizationParameter: (_b = options === null || options === void 0 ? void 0 : options.quantization) !== null && _b !== void 0 ? _b : 18,
                fps: options === null || options === void 0 ? void 0 : options.fps,
                pass: {
                    getImageData: (runtime, width, height) => this.renderer.getImageRaw(runtime, { width, height }, options === null || options === void 0 ? void 0 : options.postprocessing),
                    updateBackground: () => this.renderer.imagePass.updateBackground(),
                },
            });
            return movie;
        });
        return this.runTask(task, { useOverlay: true });
    }
    /** Render plugin state snapshots animation and save to a MP4 file */
    async saveAnimation(outPath, options) {
        const movie = await this.getAnimation(options);
        await new Promise(resolve => {
            fs.writeFile(outPath, movie, () => resolve());
        });
    }
}
