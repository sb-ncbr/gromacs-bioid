"use strict";
/**
 * Copyright (c) 2023-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Adam Midlik <midlik@gmail.com>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.MolstarTreeSchema = void 0;
const object_1 = require("../../../../mol-util/object");
const field_schema_1 = require("../generic/field-schema");
const params_schema_1 = require("../generic/params-schema");
const tree_schema_1 = require("../generic/tree-schema");
const mvs_tree_1 = require("../mvs/mvs-tree");
const param_types_1 = require("../mvs/param-types");
/** Schema for `MolstarTree` (intermediate tree representation between `MVSTree` and a real Molstar state) */
exports.MolstarTreeSchema = (0, tree_schema_1.TreeSchema)({
    rootKind: 'root',
    nodes: {
        ...mvs_tree_1.FullMVSTreeSchema.nodes,
        download: {
            ...mvs_tree_1.FullMVSTreeSchema.nodes.download,
            params: (0, params_schema_1.SimpleParamsSchema)({
                ...mvs_tree_1.FullMVSTreeSchema.nodes.download.params.fields,
                is_binary: (0, field_schema_1.RequiredField)(field_schema_1.bool, 'Specifies whether file is downloaded as bytes array or string'),
            }),
        },
        parse: {
            ...mvs_tree_1.FullMVSTreeSchema.nodes.parse,
            params: (0, params_schema_1.SimpleParamsSchema)({
                format: (0, field_schema_1.RequiredField)(param_types_1.MolstarParseFormatT, 'File format'),
            }),
        },
        /** Auxiliary node corresponding to Molstar's TrajectoryFrom*. */
        trajectory: {
            description: "Auxiliary node corresponding to Molstar's TrajectoryFrom*.",
            parent: ['parse'],
            params: (0, params_schema_1.SimpleParamsSchema)({
                format: (0, field_schema_1.RequiredField)(param_types_1.MolstarParseFormatT, 'File format'),
                ...(0, object_1.pickObjectKeys)(mvs_tree_1.FullMVSTreeSchema.nodes.structure.params.fields, ['block_header', 'block_index']),
            }),
        },
        /** Auxiliary node corresponding to Molstar's ModelFromTrajectory. */
        model: {
            description: "Auxiliary node corresponding to Molstar's ModelFromTrajectory.",
            parent: ['trajectory'],
            params: (0, params_schema_1.SimpleParamsSchema)((0, object_1.pickObjectKeys)(mvs_tree_1.FullMVSTreeSchema.nodes.structure.params.fields, ['model_index'])),
        },
        /** Auxiliary node corresponding to Molstar's StructureFromModel. */
        structure: {
            ...mvs_tree_1.FullMVSTreeSchema.nodes.structure,
            parent: ['model'],
            params: (0, params_schema_1.SimpleParamsSchema)((0, object_1.omitObjectKeys)(mvs_tree_1.FullMVSTreeSchema.nodes.structure.params.fields, ['block_header', 'block_index', 'model_index'])),
        },
    }
});
