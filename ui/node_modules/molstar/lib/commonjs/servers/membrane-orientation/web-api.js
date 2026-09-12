"use strict";
/**
 * Copyright (c) 2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Sebastian Bittrich <sebastian.bittrich@rcsb.org>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.initWebApi = initWebApi;
const config_1 = require("./config");
const swagger_ui_1 = require("../common/swagger-ui");
const web_schema_1 = require("./web-schema");
const prop_1 = require("../../extensions/anvil/prop");
const synchronous_1 = require("../../mol-task/execution/synchronous");
const assets_1 = require("../../mol-util/assets");
const cif_1 = require("../../mol-io/reader/cif");
const structure_1 = require("../../mol-model/structure");
const mmcif_1 = require("../../mol-model-formats/structure/mmcif");
const algorithm_1 = require("../../extensions/anvil/algorithm");
const param_definition_1 = require("../../mol-util/param-definition");
const console_logger_1 = require("../../mol-util/console-logger");
const assetManager = new assets_1.AssetManager();
function initWebApi(app) {
    function makePath(p) {
        return config_1.MembraneServerConfig.apiPrefix + '/' + p;
    }
    app.get(makePath('predict/:id/'), async (req, res) => predictMembraneOrientation(req, res));
    app.get(makePath('openapi.json'), (_, res) => {
        res.writeHead(200, {
            'Content-Type': 'application/json; charset=utf-8',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'X-Requested-With'
        });
        res.end(JSON.stringify((0, web_schema_1.getSchema)()));
    });
    app.use(makePath(''), (0, swagger_ui_1.swaggerUiAssetsHandler)());
    app.get(makePath(''), (0, swagger_ui_1.swaggerUiIndexHandler)({
        openapiJsonUrl: makePath('openapi.json'),
        apiPrefix: config_1.MembraneServerConfig.apiPrefix,
        title: 'MembraneServer API',
        shortcutIconLink: web_schema_1.shortcutIconLink
    }));
}
async function predictMembraneOrientation(req, res) {
    var _a;
    try {
        const ctx = { runtime: synchronous_1.SyncRuntimeContext, assetManager };
        const entryId = req.params.id;
        const assemblyId = (_a = req.query.assemblyId) !== null && _a !== void 0 ? _a : '1';
        const p = parseParams(req);
        console_logger_1.ConsoleLogger.log('predictMembraneOrientation', `${entryId}-${assemblyId} with params: ${JSON.stringify(p)}`);
        const cif = await downloadFromPdb(entryId);
        const models = await getModels(cif);
        const structure = await getStructure(models.representative, assemblyId);
        await prop_1.MembraneOrientationProvider.attach(ctx, structure, p);
        const data = prop_1.MembraneOrientationProvider.get(structure).value;
        res.status(200).json(data);
    }
    catch (e) {
        const error = 'Failed to compute membrane orientation';
        console_logger_1.ConsoleLogger.error(error, e);
        res.status(500).json({ error });
    }
}
const defaults = param_definition_1.ParamDefinition.getDefaultValues(algorithm_1.ANVILParams);
function parseParams(req) {
    const { numberOfSpherePoints = defaults.numberOfSpherePoints, stepSize = defaults.stepSize, minThickness = defaults.minThickness, maxThickness = defaults.maxThickness, asaCutoff = defaults.asaCutoff, adjust = defaults.adjust, tmdetDefinition = defaults.tmdetDefinition, } = req.query;
    return {
        numberOfSpherePoints: Number(numberOfSpherePoints),
        stepSize: Number(stepSize),
        minThickness: Number(minThickness),
        maxThickness: Number(maxThickness),
        asaCutoff: Number(asaCutoff),
        adjust: Number(adjust),
        tmdetDefinition: tmdetDefinition === 'true',
    };
}
async function parseCif(data) {
    const comp = cif_1.CIF.parse(data);
    const parsed = await comp.run();
    if (parsed.isError)
        throw parsed;
    return parsed.result;
}
async function downloadCif(url, isBinary) {
    const data = await fetch(url);
    return parseCif(isBinary ? new Uint8Array(await data.arrayBuffer()) : await data.text());
}
async function downloadFromPdb(pdb) {
    const parsed = await downloadCif(config_1.MembraneServerConfig.bcifSource(pdb), true);
    return parsed.blocks[0];
}
async function getModels(frame) {
    return await (0, mmcif_1.trajectoryFromMmCIF)(frame).run();
}
async function getStructure(model, assemblyId) {
    const modelStructure = structure_1.Structure.ofModel(model);
    return await structure_1.StructureSymmetry.buildAssembly(modelStructure, assemblyId).run();
}
