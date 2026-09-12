"use strict";
/**
 * Copyright (c) 2023-2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Adam Midlik <midlik@gmail.com>
 * @author David Sehnal <david.sehnal@gmail.com>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.FullMVSTreeSchema = exports.MVSTreeSchema = exports.DefaultColor = void 0;
const field_schema_1 = require("../generic/field-schema");
const params_schema_1 = require("../generic/params-schema");
const tree_schema_1 = require("../generic/tree-schema");
const mvs_tree_representations_1 = require("./mvs-tree-representations");
const mvs_tree_primitives_1 = require("./mvs-tree-primitives");
const param_types_1 = require("./param-types");
const _DataFromUriParams = {
    /** URL of the annotation resource. */
    uri: (0, field_schema_1.RequiredField)(field_schema_1.str, 'URL of the annotation resource.'),
    /** Format of the annotation resource. */
    format: (0, field_schema_1.RequiredField)(param_types_1.SchemaFormatT, 'Format of the annotation resource.'),
    /** Annotation schema defines what fields in the annotation will be taken into account. */
    schema: (0, field_schema_1.RequiredField)(param_types_1.SchemaT, 'Annotation schema defines what fields in the annotation will be taken into account.'),
    /** Header of the CIF block to read annotation from (only applies when `format` is `"cif"` or `"bcif"`). If `null`, block is selected based on `block_index`. */
    block_header: (0, field_schema_1.OptionalField)((0, field_schema_1.nullable)(field_schema_1.str), null, 'Header of the CIF block to read annotation from (only applies when `format` is `"cif"` or `"bcif"`). If `null`, block is selected based on `block_index`.'),
    /** 0-based index of the CIF block to read annotation from (only applies when `format` is `"cif"` or `"bcif"` and `block_header` is `null`). */
    block_index: (0, field_schema_1.OptionalField)(field_schema_1.int, 0, '0-based index of the CIF block to read annotation from (only applies when `format` is `"cif"` or `"bcif"` and `block_header` is `null`).'),
    /** Name of the CIF category to read annotation from (only applies when `format` is `"cif"` or `"bcif"`). If `null`, the first category in the block is used. */
    category_name: (0, field_schema_1.OptionalField)((0, field_schema_1.nullable)(field_schema_1.str), null, 'Name of the CIF category to read annotation from (only applies when `format` is `"cif"` or `"bcif"`). If `null`, the first category in the block is used.'),
    /** Name of the column in CIF or field name (key) in JSON that contains the dependent variable (color/label/tooltip/component_id...). The default value is 'color'/'label'/'tooltip'/'component' depending on the node type */
    field_name: (0, field_schema_1.RequiredField)(field_schema_1.str, 'Name of the column in CIF or field name (key) in JSON that contains the dependent variable (color/label/tooltip/component_id...).'),
};
const _DataFromSourceParams = {
    /** Annotation schema defines what fields in the annotation will be taken into account. */
    schema: (0, field_schema_1.RequiredField)(param_types_1.SchemaT, 'Annotation schema defines what fields in the annotation will be taken into account.'),
    /** Header of the CIF block to read annotation from. If `null`, block is selected based on `block_index`. */
    block_header: (0, field_schema_1.OptionalField)((0, field_schema_1.nullable)(field_schema_1.str), null, 'Header of the CIF block to read annotation from. If `null`, block is selected based on `block_index`.'),
    /** 0-based index of the CIF block to read annotation from (only applies when `block_header` is `null`). */
    block_index: (0, field_schema_1.OptionalField)(field_schema_1.int, 0, '0-based index of the CIF block to read annotation from (only applies when `block_header` is `null`).'),
    /** Name of the CIF category to read annotation from. If `null`, the first category in the block is used. */
    category_name: (0, field_schema_1.OptionalField)((0, field_schema_1.nullable)(field_schema_1.str), null, 'Name of the CIF category to read annotation from. If `null`, the first category in the block is used.'),
    /** Name of the column in CIF or field name (key) in JSON that contains the dependent variable (color/label/tooltip/component_id...). The default value is 'color'/'label'/'tooltip'/'component' depending on the node type */
    field_name: (0, field_schema_1.RequiredField)(field_schema_1.str, 'Name of the column in CIF or field name (key) in JSON that contains the dependent variable (color/label/tooltip/component_id...).'),
};
/** Color to be used e.g. for representations without 'color' node */
exports.DefaultColor = 'white';
/** Schema for `MVSTree` (MolViewSpec tree) */
exports.MVSTreeSchema = (0, tree_schema_1.TreeSchema)({
    rootKind: 'root',
    nodes: {
        /** Auxiliary node kind that only appears as the tree root. */
        root: {
            description: 'Auxiliary node kind that only appears as the tree root.',
            parent: [],
            params: (0, params_schema_1.SimpleParamsSchema)({}),
        },
        /** This node instructs to retrieve a data resource. */
        download: {
            description: 'This node instructs to retrieve a data resource.',
            parent: ['root'],
            params: (0, params_schema_1.SimpleParamsSchema)({
                /** URL of the data resource. */
                url: (0, field_schema_1.RequiredField)(field_schema_1.str, 'URL of the data resource.'),
            }),
        },
        /** This node instructs to parse a data resource. */
        parse: {
            description: 'This node instructs to parse a data resource.',
            parent: ['download'],
            params: (0, params_schema_1.SimpleParamsSchema)({
                /** Format of the input data resource. */
                format: (0, field_schema_1.RequiredField)(param_types_1.ParseFormatT, 'Format of the input data resource.'),
            }),
        },
        /** This node instructs to create a structure from a parsed data resource. "Structure" refers to an internal representation of molecular coordinates without any visual representation. */
        structure: {
            description: 'This node instructs to create a structure from a parsed data resource. "Structure" refers to an internal representation of molecular coordinates without any visual representation.',
            parent: ['parse'],
            params: (0, params_schema_1.SimpleParamsSchema)({
                /** Type of structure to be created (`"model"` for original model coordinates, `"assembly"` for assembly structure, `"symmetry"` for a set of crystal unit cells based on Miller indices, `"symmetry_mates"` for a set of asymmetric units within a radius from the original model). */
                type: (0, field_schema_1.RequiredField)(param_types_1.StructureTypeT, 'Type of structure to be created (`"model"` for original model coordinates, `"assembly"` for assembly structure, `"symmetry"` for a set of crystal unit cells based on Miller indices, `"symmetry_mates"` for a set of asymmetric units within a radius from the original model).'),
                /** Header of the CIF block to read coordinates from (only applies when the input data are from CIF or BinaryCIF). If `null`, block is selected based on `block_index`. */
                block_header: (0, field_schema_1.OptionalField)((0, field_schema_1.nullable)(field_schema_1.str), null, 'Header of the CIF block to read coordinates from (only applies when the input data are from CIF or BinaryCIF). If `null`, block is selected based on `block_index`.'),
                /** 0-based index of the CIF block to read coordinates from (only applies when the input data are from CIF or BinaryCIF and `block_header` is `null`). */
                block_index: (0, field_schema_1.OptionalField)(field_schema_1.int, 0, '0-based index of the CIF block to read coordinates from (only applies when the input data are from CIF or BinaryCIF and `block_header` is `null`).'),
                /** 0-based index of model in case the input data contain multiple models. */
                model_index: (0, field_schema_1.OptionalField)(field_schema_1.int, 0, '0-based index of model in case the input data contain multiple models.'),
                /** Assembly identifier (only applies when `kind` is `"assembly"`). If `null`, the first assembly is selected. */
                assembly_id: (0, field_schema_1.OptionalField)((0, field_schema_1.nullable)(field_schema_1.str), null, 'Assembly identifier (only applies when `kind` is `"assembly"`). If `null`, the first assembly is selected.'),
                /** Distance (in Angstroms) from the original model in which asymmetric units should be included (only applies when `kind` is `"symmetry_mates"`). */
                radius: (0, field_schema_1.OptionalField)(field_schema_1.float, 5, 'Distance (in Angstroms) from the original model in which asymmetric units should be included (only applies when `kind` is `"symmetry_mates"`).'),
                /** Miller indices of the bottom-left unit cell to be included (only applies when `kind` is `"symmetry"`). */
                ijk_min: (0, field_schema_1.OptionalField)((0, field_schema_1.tuple)([field_schema_1.int, field_schema_1.int, field_schema_1.int]), [-1, -1, -1], 'Miller indices of the bottom-left unit cell to be included (only applies when `kind` is `"symmetry"`).'),
                /** Miller indices of the top-right unit cell to be included (only applies when `kind` is `"symmetry"`). */
                ijk_max: (0, field_schema_1.OptionalField)((0, field_schema_1.tuple)([field_schema_1.int, field_schema_1.int, field_schema_1.int]), [1, 1, 1], 'Miller indices of the top-right unit cell to be included (only applies when `kind` is `"symmetry"`).'),
            }),
        },
        /** This node instructs to rotate and/or translate structure coordinates. */
        transform: {
            description: 'This node instructs to rotate and/or translate structure coordinates.',
            parent: ['structure'],
            params: (0, params_schema_1.SimpleParamsSchema)({
                /** Rotation matrix (3x3 matrix flattened in column major format (j*3+i indexing), this is equivalent to Fortran-order in numpy). This matrix will multiply the structure coordinates from the left. The default value is the identity matrix (corresponds to no rotation). */
                rotation: (0, field_schema_1.OptionalField)(param_types_1.Matrix, [1, 0, 0, 0, 1, 0, 0, 0, 1], 'Rotation matrix (3x3 matrix flattened in column major format (j*3+i indexing), this is equivalent to Fortran-order in numpy). This matrix will multiply the structure coordinates from the left. The default value is the identity matrix (corresponds to no rotation).'),
                /** Translation vector, applied to the structure coordinates after rotation. The default value is the zero vector (corresponds to no translation). */
                translation: (0, field_schema_1.OptionalField)(param_types_1.Vector3, [0, 0, 0], 'Translation vector, applied to the structure coordinates after rotation. The default value is the zero vector (corresponds to no translation).'),
            }),
        },
        /** This node instructs to create a component (i.e. a subset of the parent structure). */
        component: {
            description: 'This node instructs to create a component (i.e. a subset of the parent structure).',
            parent: ['structure'],
            params: (0, params_schema_1.SimpleParamsSchema)({
                /** Defines what part of the parent structure should be included in this component. */
                selector: (0, field_schema_1.RequiredField)((0, field_schema_1.union)([param_types_1.ComponentSelectorT, param_types_1.ComponentExpressionT, (0, field_schema_1.list)(param_types_1.ComponentExpressionT)]), 'Defines what part of the parent structure should be included in this component.'),
            }),
        },
        /** This node instructs to create a component defined by an external annotation resource. */
        component_from_uri: {
            description: 'This node instructs to create a component defined by an external annotation resource.',
            parent: ['structure'],
            params: (0, params_schema_1.SimpleParamsSchema)({
                ..._DataFromUriParams,
                /** Name of the column in CIF or field name (key) in JSON that contains the component identifier. */
                field_name: (0, field_schema_1.OptionalField)(field_schema_1.str, 'component', 'Name of the column in CIF or field name (key) in JSON that contains the component identifier.'),
                /** List of component identifiers (i.e. values in the field given by `field_name`) which should be included in this component. If `null`, component identifiers are ignored (all annotation rows are included), and `field_name` field can be dropped from the annotation. */
                field_values: (0, field_schema_1.OptionalField)((0, field_schema_1.nullable)((0, field_schema_1.list)(field_schema_1.str)), null, 'List of component identifiers (i.e. values in the field given by `field_name`) which should be included in this component. If `null`, component identifiers are ignored (all annotation rows are included), and `field_name` field can be dropped from the annotation.'),
            }),
        },
        /** This node instructs to create a component defined by an annotation resource included in the same file this structure was loaded from. Only applicable if the structure was loaded from an mmCIF or BinaryCIF file. */
        component_from_source: {
            description: 'This node instructs to create a component defined by an annotation resource included in the same file this structure was loaded from. Only applicable if the structure was loaded from an mmCIF or BinaryCIF file.',
            parent: ['structure'],
            params: (0, params_schema_1.SimpleParamsSchema)({
                ..._DataFromSourceParams,
                /** Name of the column in CIF or field name (key) in JSON that contains the component identifier. */
                field_name: (0, field_schema_1.OptionalField)(field_schema_1.str, 'component', 'Name of the column in CIF or field name (key) in JSON that contains the component identifier.'),
                /** List of component identifiers (i.e. values in the field given by `field_name`) which should be included in this component. If `null`, component identifiers are ignored (all annotation rows are included), and `field_name` field can be dropped from the annotation. */
                field_values: (0, field_schema_1.OptionalField)((0, field_schema_1.nullable)((0, field_schema_1.list)(field_schema_1.str)), null, 'List of component identifiers (i.e. values in the field given by `field_name`) which should be included in this component. If `null`, component identifiers are ignored (all annotation rows are included), and `field_name` field can be dropped from the annotation.'),
            }),
        },
        /** This node instructs to create a visual representation of a component. */
        representation: {
            description: 'This node instructs to create a visual representation of a component.',
            parent: ['component', 'component_from_uri', 'component_from_source'],
            params: mvs_tree_representations_1.MVSRepresentationParams,
        },
        /** This node instructs to create a volume from a parsed data resource. "Volume" refers to an internal representation of volumetric data without any visual representation. */
        volume: {
            description: 'This node instructs to create a volume from a parsed data resource. "Volume" refers to an internal representation of volumetric data without any visual representation.',
            parent: ['parse'],
            params: (0, params_schema_1.SimpleParamsSchema)({
                channel_id: (0, field_schema_1.OptionalField)((0, field_schema_1.nullable)(field_schema_1.str), null, 'Channel identifier (only applies when the input data contain multiple channels).'),
            }),
        },
        /** This node instructs to create a visual representation of a volume. */
        volume_representation: {
            description: 'This node instructs to create a visual representation of a volume.',
            parent: ['volume'],
            params: mvs_tree_representations_1.MVSVolumeRepresentationParams,
        },
        /** This node instructs to apply color to a visual representation. */
        color: {
            description: 'This node instructs to apply color to a visual representation.',
            parent: ['representation', 'volume_representation'],
            params: (0, params_schema_1.SimpleParamsSchema)({
                /** Color to apply to the representation. Can be either an X11 color name (e.g. `"red"`) or a hexadecimal code (e.g. `"#FF0011"`). */
                color: (0, field_schema_1.OptionalField)(param_types_1.ColorT, exports.DefaultColor, 'Color to apply to the representation. Can be either an X11 color name (e.g. `"red"`) or a hexadecimal code (e.g. `"#FF0011"`).'),
                /** Defines to what part of the representation this color should be applied. */
                selector: (0, field_schema_1.OptionalField)((0, field_schema_1.union)([param_types_1.ComponentSelectorT, param_types_1.ComponentExpressionT, (0, field_schema_1.list)(param_types_1.ComponentExpressionT)]), 'all', 'Defines to what part of the representation this color should be applied.'),
            }),
        },
        /** This node instructs to apply colors to a visual representation. The colors are defined by an external annotation resource. */
        color_from_uri: {
            description: 'This node instructs to apply colors to a visual representation. The colors are defined by an external annotation resource.',
            parent: ['representation'],
            params: (0, params_schema_1.SimpleParamsSchema)({
                ..._DataFromUriParams,
                /** Name of the column in CIF or field name (key) in JSON that contains the color. */
                field_name: (0, field_schema_1.OptionalField)(field_schema_1.str, 'color', 'Name of the column in CIF or field name (key) in JSON that contains the color.'),
            }),
        },
        /** This node instructs to apply colors to a visual representation. The colors are defined by an annotation resource included in the same file this structure was loaded from. Only applicable if the structure was loaded from an mmCIF or BinaryCIF file. */
        color_from_source: {
            description: 'This node instructs to apply colors to a visual representation. The colors are defined by an annotation resource included in the same file this structure was loaded from. Only applicable if the structure was loaded from an mmCIF or BinaryCIF file.',
            parent: ['representation'],
            params: (0, params_schema_1.SimpleParamsSchema)({
                ..._DataFromSourceParams,
                /** Name of the column in CIF or field name (key) in JSON that contains the color. */
                field_name: (0, field_schema_1.OptionalField)(field_schema_1.str, 'color', 'Name of the column in CIF or field name (key) in JSON that contains the color.'),
            }),
        },
        /** This node instructs to apply opacity/transparency to a visual representation. */
        opacity: {
            description: 'This node instructs to apply opacity/transparency to a visual representation.',
            parent: ['representation', 'volume_representation'],
            params: (0, params_schema_1.SimpleParamsSchema)({
                /** Opacity of a representation. 0.0: fully transparent, 1.0: fully opaque. */
                opacity: (0, field_schema_1.RequiredField)(field_schema_1.float, 'Opacity of a representation. 0.0: fully transparent, 1.0: fully opaque.'),
            }),
        },
        /** This node instructs to add a label (textual visual representation) to a component. */
        label: {
            description: 'This node instructs to add a label (textual visual representation) to a component.',
            parent: ['component', 'component_from_uri', 'component_from_source'],
            params: (0, params_schema_1.SimpleParamsSchema)({
                /** Content of the shown label. */
                text: (0, field_schema_1.RequiredField)(field_schema_1.str, 'Content of the shown label.'),
            }),
        },
        /** This node instructs to add labels (textual visual representations) to parts of a structure. The labels are defined by an external annotation resource. */
        label_from_uri: {
            description: 'This node instructs to add labels (textual visual representations) to parts of a structure. The labels are defined by an external annotation resource.',
            parent: ['structure'],
            params: (0, params_schema_1.SimpleParamsSchema)({
                ..._DataFromUriParams,
                /** Name of the column in CIF or field name (key) in JSON that contains the label text. */
                field_name: (0, field_schema_1.OptionalField)(field_schema_1.str, 'label', 'Name of the column in CIF or field name (key) in JSON that contains the label text.'),
            }),
        },
        /** This node instructs to add labels (textual visual representations) to parts of a structure. The labels are defined by an annotation resource included in the same file this structure was loaded from. Only applicable if the structure was loaded from an mmCIF or BinaryCIF file. */
        label_from_source: {
            description: 'This node instructs to add labels (textual visual representations) to parts of a structure. The labels are defined by an annotation resource included in the same file this structure was loaded from. Only applicable if the structure was loaded from an mmCIF or BinaryCIF file.',
            parent: ['structure'],
            params: (0, params_schema_1.SimpleParamsSchema)({
                ..._DataFromSourceParams,
                /** Name of the column in CIF or field name (key) in JSON that contains the label text. */
                field_name: (0, field_schema_1.OptionalField)(field_schema_1.str, 'label', 'Name of the column in CIF or field name (key) in JSON that contains the label text.'),
            }),
        },
        /** This node instructs to add a tooltip to a component. "Tooltip" is a text which is not a part of the visualization but should be presented to the users when they interact with the component (typically, the tooltip will be shown somewhere on the screen when the user hovers over a visual representation of the component). */
        tooltip: {
            description: 'This node instructs to add a tooltip to a component. "Tooltip" is a text which is not a part of the visualization but should be presented to the users when they interact with the component (typically, the tooltip will be shown somewhere on the screen when the user hovers over a visual representation of the component).',
            parent: ['component', 'component_from_uri', 'component_from_source'],
            params: (0, params_schema_1.SimpleParamsSchema)({
                /** Content of the shown tooltip. */
                text: (0, field_schema_1.RequiredField)(field_schema_1.str, 'Content of the shown tooltip.'),
            }),
        },
        /** This node instructs to add tooltips to parts of a structure. The tooltips are defined by an external annotation resource. */
        tooltip_from_uri: {
            description: 'This node instructs to add tooltips to parts of a structure. The tooltips are defined by an external annotation resource.',
            parent: ['structure'],
            params: (0, params_schema_1.SimpleParamsSchema)({
                ..._DataFromUriParams,
                /** Name of the column in CIF or field name (key) in JSON that contains the tooltip text. */
                field_name: (0, field_schema_1.OptionalField)(field_schema_1.str, 'tooltip', 'Name of the column in CIF or field name (key) in JSON that contains the tooltip text.'),
            }),
        },
        /** This node instructs to add tooltips to parts of a structure. The tooltips are defined by an annotation resource included in the same file this structure was loaded from. Only applicable if the structure was loaded from an mmCIF or BinaryCIF file. */
        tooltip_from_source: {
            description: 'This node instructs to add tooltips to parts of a structure. The tooltips are defined by an annotation resource included in the same file this structure was loaded from. Only applicable if the structure was loaded from an mmCIF or BinaryCIF file.',
            parent: ['structure'],
            params: (0, params_schema_1.SimpleParamsSchema)({
                ..._DataFromSourceParams,
                /** Name of the column in CIF or field name (key) in JSON that contains the tooltip text. */
                field_name: (0, field_schema_1.OptionalField)(field_schema_1.str, 'tooltip', 'Name of the column in CIF or field name (key) in JSON that contains the tooltip text.'),
            }),
        },
        /** This node instructs to set the camera focus to a component (zoom in). */
        focus: {
            description: 'This node instructs to set the camera focus to a component (zoom in).',
            parent: ['root', 'component', 'component_from_uri', 'component_from_source', 'primitives', 'primitives_from_uri', 'volume', 'volume_representation'],
            params: (0, params_schema_1.SimpleParamsSchema)({
                /** Vector describing the direction of the view (camera position -> focused target). */
                direction: (0, field_schema_1.OptionalField)(param_types_1.Vector3, [0, 0, -1], 'Vector describing the direction of the view (camera position -> focused target).'),
                /** Vector which will be aligned with the screen Y axis. */
                up: (0, field_schema_1.OptionalField)(param_types_1.Vector3, [0, 1, 0], 'Vector which will be aligned with the screen Y axis.'),
                /** Radius of the focused sphere (overrides `radius_factor` and `radius_extra`. */
                radius: (0, field_schema_1.OptionalField)((0, field_schema_1.nullable)(field_schema_1.float), null, 'Radius of the focused sphere (overrides `radius_factor` and `radius_extra`).'),
                /** Radius of the focused sphere relative to the radius of parent component (default: 1). Focused radius = component_radius * radius_factor + radius_extent. */
                radius_factor: (0, field_schema_1.OptionalField)(field_schema_1.float, 1, 'Radius of the focused sphere relative to the radius of parent component (default: 1). Focused radius = component_radius * radius_factor + radius_extent.'),
                /** Addition to the radius of the focused sphere, if computed from the radius of parent component (default: 0). Focused radius = component_radius * radius_factor + radius_extent. */
                radius_extent: (0, field_schema_1.OptionalField)(field_schema_1.float, 0, 'Addition to the radius of the focused sphere, if computed from the radius of parent component (default: 0). Focused radius = component_radius * radius_factor + radius_extent.'),
            }),
        },
        /** This node instructs to set the camera position and orientation. */
        camera: {
            description: 'This node instructs to set the camera position and orientation.',
            parent: ['root'],
            params: (0, params_schema_1.SimpleParamsSchema)({
                /** Coordinates of the point in space at which the camera is pointing. */
                target: (0, field_schema_1.RequiredField)(param_types_1.Vector3, 'Coordinates of the point in space at which the camera is pointing.'),
                /** Coordinates of the camera. */
                position: (0, field_schema_1.RequiredField)(param_types_1.Vector3, 'Coordinates of the camera.'),
                /** Vector which will be aligned with the screen Y axis. */
                up: (0, field_schema_1.OptionalField)(param_types_1.Vector3, [0, 1, 0], 'Vector which will be aligned with the screen Y axis.'),
            }),
        },
        /** This node sets canvas properties. */
        canvas: {
            description: 'This node sets canvas properties.',
            parent: ['root'],
            params: (0, params_schema_1.SimpleParamsSchema)({
                /** Color of the canvas background. Can be either an X11 color name (e.g. `"red"`) or a hexadecimal code (e.g. `"#FF0011"`). */
                background_color: (0, field_schema_1.RequiredField)(param_types_1.ColorT, 'Color of the canvas background. Can be either an X11 color name (e.g. `"red"`) or a hexadecimal code (e.g. `"#FF0011"`).'),
            }),
        },
        primitives: {
            description: 'This node groups a list of geometrical primitives',
            parent: ['structure', 'root'],
            params: (0, params_schema_1.SimpleParamsSchema)({
                /** Default color for primitives in this group. */
                color: (0, field_schema_1.OptionalField)(param_types_1.ColorT, 'white', 'Default color for primitives in this group.'),
                /** Default label color for primitives in this group. */
                label_color: (0, field_schema_1.OptionalField)(param_types_1.ColorT, 'white', 'Default label color for primitives in this group.'),
                /** Default tooltip for primitives in this group. */
                tooltip: (0, field_schema_1.OptionalField)((0, field_schema_1.nullable)(field_schema_1.str), null, 'Default tooltip for primitives in this group.'),
                /** Opacity of primitive geometry in this group. */
                opacity: (0, field_schema_1.OptionalField)(field_schema_1.float, 1, 'Opacity of primitive geometry in this group.'),
                /** Opacity of primitive labels in this group. */
                label_opacity: (0, field_schema_1.OptionalField)(field_schema_1.float, 1, 'Opacity of primitive labels in this group.'),
                /** Instances of this primitive group defined as 4x4 column major (j * 4 + i indexing) transformation matrices. */
                instances: (0, field_schema_1.OptionalField)((0, field_schema_1.nullable)((0, field_schema_1.list)(param_types_1.Matrix)), null, 'Instances of this primitive group defined as 4x4 column major (j * 4 + i indexing) transformation matrices.'),
            }),
        },
        primitives_from_uri: {
            description: 'This node loads a list of primitives from URI',
            parent: ['structure', 'root'],
            params: (0, params_schema_1.SimpleParamsSchema)({
                /** Location of the resource. */
                uri: (0, field_schema_1.RequiredField)(field_schema_1.str, 'Location of the resource.'),
                /** Format of the data. */
                format: (0, field_schema_1.RequiredField)((0, field_schema_1.literal)('mvs-node-json'), 'Format of the data.'),
                /** List of nodes the data are referencing. */
                references: (0, field_schema_1.OptionalField)(param_types_1.StrList, [], 'List of nodes the data are referencing.'),
            }),
        },
        primitive: {
            description: 'This node represents a geometrical primitive',
            parent: ['primitives'],
            params: mvs_tree_primitives_1.MVSPrimitiveParams,
        },
    }
});
/** Schema for `MVSTree` (MolViewSpec tree with all params provided) */
exports.FullMVSTreeSchema = (0, tree_schema_1.TreeSchemaWithAllRequired)(exports.MVSTreeSchema);
