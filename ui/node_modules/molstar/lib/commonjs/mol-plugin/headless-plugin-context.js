"use strict";
/**
 * Copyright (c) 2023-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Adam Midlik <midlik@gmail.com>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.HeadlessPluginContext = void 0;
const tslib_1 = require("tslib");
const fs_1 = tslib_1.__importDefault(require("fs"));
const mp4_export_1 = require("../extensions/mp4-export");
const encoder_1 = require("../extensions/mp4-export/encoder");
const state_snapshots_1 = require("../mol-plugin-state/animation/built-in/state-snapshots");
const mol_task_1 = require("../mol-task");
const context_1 = require("./context");
const headless_screenshot_1 = require("./util/headless-screenshot");
/** PluginContext that can be used in Node.js (without DOM) */
class HeadlessPluginContext extends context_1.PluginContext {
    /** External modules (`gl` and optionally `pngjs` and `jpeg-js`) must be provided to the constructor (this is to avoid Mol* being dependent on these packages which are only used here) */
    constructor(externalModules, spec, canvasSize = { width: 640, height: 480 }, rendererOptions) {
        super(spec);
        this.renderer = new headless_screenshot_1.HeadlessScreenshotHelper(externalModules, canvasSize, undefined, rendererOptions);
        this.canvas3d = this.renderer.canvas3d;
    }
    /** Render the current plugin state and save to a PNG or JPEG file */
    async saveImage(outPath, imageSize, props, format, jpegQuality = 90) {
        const task = mol_task_1.Task.create('Render Screenshot', async (ctx) => {
            this.canvas3d.commit(true);
            return await this.renderer.saveImage(ctx, outPath, imageSize, props, format, jpegQuality);
        });
        return this.runTask(task);
    }
    /** Render the current plugin state and return as raw image data */
    async getImageRaw(imageSize, props) {
        const task = mol_task_1.Task.create('Render Screenshot', async (ctx) => {
            this.canvas3d.commit(true);
            return await this.renderer.getImageRaw(ctx, imageSize, props);
        });
        return this.runTask(task);
    }
    /** Render the current plugin state and return as a PNG object */
    async getImagePng(imageSize, props) {
        const task = mol_task_1.Task.create('Render Screenshot', async (ctx) => {
            this.canvas3d.commit(true);
            return await this.renderer.getImagePng(ctx, imageSize, props);
        });
        return this.runTask(task);
    }
    /** Render the current plugin state and return as a JPEG object */
    async getImageJpeg(imageSize, props, jpegQuality = 90) {
        const task = mol_task_1.Task.create('Render Screenshot', async (ctx) => {
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
            fs_1.default.writeFile(outPath, snapshot_json, () => resolve());
        });
    }
    /** Render plugin state snapshots animation and return as raw MP4 data */
    async getAnimation(options) {
        if (!this.state.hasBehavior(mp4_export_1.Mp4Export)) {
            throw new Error('PluginContext must have Mp4Export extension registered in order to save animation.');
        }
        const task = mol_task_1.Task.create('Export Animation', async (ctx) => {
            var _a, _b;
            const { width, height } = (_a = options === null || options === void 0 ? void 0 : options.size) !== null && _a !== void 0 ? _a : this.renderer.canvasSize;
            const movie = await (0, encoder_1.encodeMp4Animation)(this, ctx, {
                animation: { definition: state_snapshots_1.AnimateStateSnapshots, params: {} },
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
            fs_1.default.writeFile(outPath, movie, () => resolve());
        });
    }
}
exports.HeadlessPluginContext = HeadlessPluginContext;
