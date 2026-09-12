"use strict";
/**
 * Copyright (c) 2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alex Chan <smalldirkalex@gmail.com>
 *
 * Thanks to @author Adam Midlik <midlik@gmail.com> for the example code ../image-renderer and https://github.com/midlik/surface-calculator i can make reference to,
 *
 * Example command-line application generating and exporting PubChem SDF structures
 * Build: npm install --no-save gl  // these packages are not listed in dependencies for performance reasons
 *        npm run build
 * Run:   node lib/commonjs/examples/glb-export 2519 ../outputs_2519/
 */
Object.defineProperty(exports, "__esModule", { value: true });
const tslib_1 = require("tslib");
const argparse_1 = require("argparse");
const fs_1 = tslib_1.__importDefault(require("fs"));
const path_1 = tslib_1.__importDefault(require("path"));
const gl_1 = tslib_1.__importDefault(require("gl"));
const mol_task_1 = require("../../mol-task");
const data_1 = require("../../mol-plugin-state/transforms/data");
const glb_exporter_1 = require("../../extensions/geo-export/glb-exporter");
const geometry_1 = require("../../mol-math/geometry");
const model_1 = require("../../mol-plugin-state/transforms/model");
const representation_1 = require("../../mol-plugin-state/transforms/representation");
const headless_plugin_context_1 = require("../../mol-plugin/headless-plugin-context");
const spec_1 = require("../../mol-plugin/spec");
const data_source_1 = require("../../mol-util/data-source");
(0, data_source_1.setFSModule)(fs_1.default);
function parseArguments() {
    const parser = new argparse_1.ArgumentParser({ description: 'Example command-line application exporting .glb file of SDF structures from PubChem' });
    parser.add_argument('cid', { help: 'PubChem identifier' });
    parser.add_argument('outDirectory', { help: 'Directory for outputs' });
    const args = parser.parse_args();
    return { ...args };
}
async function main() {
    var _a;
    const args = parseArguments();
    const root = 'https://pubchem.ncbi.nlm.nih.gov/rest';
    const url = `${root}/pug/compound/cid/${args.cid}/sdf?record_type=3d`;
    console.log('PubChem CID:', args.cid);
    console.log('Source URL:', url);
    console.log('Outputs:', args.outDirectory);
    // Create a headless plugin
    const externalModules = { gl: gl_1.default };
    const plugin = new headless_plugin_context_1.HeadlessPluginContext(externalModules, (0, spec_1.DefaultPluginSpec)());
    await plugin.init();
    // Download and visualize data in the plugin
    const update = plugin.build();
    const structure = await update.toRoot()
        .apply(data_1.Download, { url, isBinary: false })
        .apply(model_1.TrajectoryFromSDF)
        .apply(model_1.ModelFromTrajectory)
        .apply(model_1.StructureFromModel)
        .apply(representation_1.StructureRepresentation3D, {
        type: { name: 'ball-and-stick', params: { size: 'physical' } },
        colorTheme: { name: 'element-symbol', params: { carbonColor: { name: 'element-symbol', params: {} } } },
        sizeTheme: { name: 'physical', params: {} },
    })
        .commit();
    const meshes = structure.data.repr.renderObjects.filter(obj => obj.type === 'mesh');
    const boundingSphere = (_a = plugin.canvas3d) === null || _a === void 0 ? void 0 : _a.boundingSphereVisible;
    const boundingBox = geometry_1.Box3D.fromSphere3D((0, geometry_1.Box3D)(), boundingSphere);
    const renderObjectExporter = new glb_exporter_1.GlbExporter(boundingBox);
    await plugin.runTask(mol_task_1.Task.create('Export Geometry', async (ctx) => {
        var _a;
        for (let i = 0, il = meshes.length; i < il; ++i) {
            await renderObjectExporter.add(meshes[i], (_a = plugin.canvas3d) === null || _a === void 0 ? void 0 : _a.webgl, ctx);
        }
        const blob = await renderObjectExporter.getBlob(ctx);
        const buffer = await blob.arrayBuffer();
        await fs_1.default.promises.writeFile(path_1.default.join(args.outDirectory, `${args.cid}.glb`), Buffer.from(buffer));
    }));
    // Cleanup
    await plugin.clear();
    plugin.dispose();
}
main();
