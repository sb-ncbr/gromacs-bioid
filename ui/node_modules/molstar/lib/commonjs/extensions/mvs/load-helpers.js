"use strict";
/**
 * Copyright (c) 2023-2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Adam Midlik <midlik@gmail.com>
 * @author David Sehnal <david.sehnal@gmail.com>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.AnnotationFromSourceKinds = exports.AnnotationFromUriKinds = void 0;
exports.transformFromRotationTranslation = transformFromRotationTranslation;
exports.transformProps = transformProps;
exports.collectAnnotationReferences = collectAnnotationReferences;
exports.collectAnnotationTooltips = collectAnnotationTooltips;
exports.collectInlineTooltips = collectInlineTooltips;
exports.collectInlineLabels = collectInlineLabels;
exports.isPhantomComponent = isPhantomComponent;
exports.structureProps = structureProps;
exports.componentPropsFromSelector = componentPropsFromSelector;
exports.prettyNameFromSelector = prettyNameFromSelector;
exports.labelFromXProps = labelFromXProps;
exports.componentFromXProps = componentFromXProps;
exports.representationProps = representationProps;
exports.alphaForNode = alphaForNode;
exports.colorThemeForNode = colorThemeForNode;
exports.makeNearestReprMap = makeNearestReprMap;
exports.volumeRepresentationProps = volumeRepresentationProps;
exports.volumeColorThemeForNode = volumeColorThemeForNode;
const linear_algebra_1 = require("../../mol-math/linear-algebra");
const volume_1 = require("../../mol-model/volume");
const array_1 = require("../../mol-util/array");
const json_1 = require("../../mol-util/json");
const string_1 = require("../../mol-util/string");
const annotation_color_theme_1 = require("./components/annotation-color-theme");
const representation_1 = require("./components/annotation-label/representation");
const multilayer_color_theme_1 = require("./components/multilayer-color-theme");
const selector_1 = require("./components/selector");
const selections_1 = require("./helpers/selections");
const utils_1 = require("./helpers/utils");
const tree_schema_1 = require("./tree/generic/tree-schema");
const tree_utils_1 = require("./tree/generic/tree-utils");
const mvs_tree_1 = require("./tree/mvs/mvs-tree");
exports.AnnotationFromUriKinds = new Set(['color_from_uri', 'component_from_uri', 'label_from_uri', 'tooltip_from_uri']);
exports.AnnotationFromSourceKinds = new Set(['color_from_source', 'component_from_source', 'label_from_source', 'tooltip_from_source']);
/** Return a 4x4 matrix representing a rotation followed by a translation */
function transformFromRotationTranslation(rotation, translation) {
    if (rotation && rotation.length !== 9)
        throw new Error(`'rotation' param for 'transform' node must be array of 9 elements, found ${rotation}`);
    if (translation && translation.length !== 3)
        throw new Error(`'translation' param for 'transform' node must be array of 3 elements, found ${translation}`);
    const T = linear_algebra_1.Mat4.identity();
    if (rotation) {
        const rotMatrix = linear_algebra_1.Mat3.fromArray((0, linear_algebra_1.Mat3)(), rotation, 0);
        ensureRotationMatrix(rotMatrix, rotMatrix);
        linear_algebra_1.Mat4.fromMat3(T, rotMatrix);
    }
    if (translation) {
        linear_algebra_1.Mat4.setTranslation(T, linear_algebra_1.Vec3.fromArray((0, linear_algebra_1.Vec3)(), translation, 0));
    }
    if (!linear_algebra_1.Mat4.isRotationAndTranslation(T))
        throw new Error(`'rotation' param for 'transform' is not a valid rotation matrix: ${rotation}`);
    return T;
}
/** Adjust values in a close-to-rotation matrix `a` to ensure it is a proper rotation matrix
 * (i.e. its columns and rows are orthonormal and determinant equal to 1, within available precission). */
function ensureRotationMatrix(out, a) {
    const x = linear_algebra_1.Vec3.fromArray(_tmpVecX, a, 0);
    const y = linear_algebra_1.Vec3.fromArray(_tmpVecY, a, 3);
    const z = linear_algebra_1.Vec3.fromArray(_tmpVecZ, a, 6);
    linear_algebra_1.Vec3.normalize(x, x);
    linear_algebra_1.Vec3.orthogonalize(y, x, y);
    linear_algebra_1.Vec3.normalize(z, linear_algebra_1.Vec3.cross(z, x, y));
    linear_algebra_1.Mat3.fromColumns(out, x, y, z);
    return out;
}
const _tmpVecX = (0, linear_algebra_1.Vec3)();
const _tmpVecY = (0, linear_algebra_1.Vec3)();
const _tmpVecZ = (0, linear_algebra_1.Vec3)();
/** Create an array of props for `TransformStructureConformation` transformers from all 'transform' nodes applied to a 'structure' node. */
function transformProps(node) {
    const result = [];
    const transforms = (0, tree_schema_1.getChildren)(node).filter(c => c.kind === 'transform');
    for (const transform of transforms) {
        const { rotation, translation } = transform.params;
        const matrix = transformFromRotationTranslation(rotation, translation);
        result.push({ transform: { name: 'matrix', params: { data: matrix, transpose: false } } });
    }
    return result;
}
/** Collect distinct annotation specs from all nodes in `tree` and set `context.annotationMap[node]` to respective annotationIds */
function collectAnnotationReferences(tree, context) {
    const distinctSpecs = {};
    (0, tree_utils_1.dfs)(tree, node => {
        var _a, _b, _c;
        let spec = undefined;
        if (exports.AnnotationFromUriKinds.has(node.kind)) {
            const p = node.params;
            spec = { source: { name: 'url', params: { url: p.uri, format: p.format } }, schema: p.schema, cifBlock: blockSpec(p.block_header, p.block_index), cifCategory: (_a = p.category_name) !== null && _a !== void 0 ? _a : undefined };
        }
        else if (exports.AnnotationFromSourceKinds.has(node.kind)) {
            const p = node.params;
            spec = { source: { name: 'source-cif', params: {} }, schema: p.schema, cifBlock: blockSpec(p.block_header, p.block_index), cifCategory: (_b = p.category_name) !== null && _b !== void 0 ? _b : undefined };
        }
        if (spec) {
            const key = (0, json_1.canonicalJsonString)(spec);
            (_c = distinctSpecs[key]) !== null && _c !== void 0 ? _c : (distinctSpecs[key] = { ...spec, id: (0, utils_1.stringHash)(key) });
            context.annotationMap.set(node, distinctSpecs[key].id);
        }
    });
    return Object.values(distinctSpecs);
}
function blockSpec(header, index) {
    if ((0, utils_1.isDefined)(header)) {
        return { name: 'header', params: { header: header } };
    }
    else {
        return { name: 'index', params: { index: index !== null && index !== void 0 ? index : 0 } };
    }
}
/** Collect annotation tooltips from all nodes in `tree` and map them to annotationIds. */
function collectAnnotationTooltips(tree, context) {
    const annotationTooltips = [];
    (0, tree_utils_1.dfs)(tree, node => {
        if (node.kind === 'tooltip_from_uri' || node.kind === 'tooltip_from_source') {
            const annotationId = context.annotationMap.get(node);
            if (annotationId) {
                annotationTooltips.push({ annotationId, fieldName: node.params.field_name });
            }
            ;
        }
    });
    return (0, array_1.arrayDistinct)(annotationTooltips);
}
/** Collect inline tooltips from all nodes in `tree`. */
function collectInlineTooltips(tree, context) {
    const inlineTooltips = [];
    (0, tree_utils_1.dfs)(tree, (node, parent) => {
        if (node.kind === 'tooltip') {
            if ((parent === null || parent === void 0 ? void 0 : parent.kind) === 'component') {
                inlineTooltips.push({
                    text: node.params.text,
                    selector: componentPropsFromSelector(parent.params.selector),
                });
            }
            else if ((parent === null || parent === void 0 ? void 0 : parent.kind) === 'component_from_uri' || (parent === null || parent === void 0 ? void 0 : parent.kind) === 'component_from_source') {
                const p = componentFromXProps(parent, context);
                if ((0, utils_1.isDefined)(p.annotationId) && (0, utils_1.isDefined)(p.fieldName) && (0, utils_1.isDefined)(p.fieldValues)) {
                    inlineTooltips.push({
                        text: node.params.text,
                        selector: {
                            name: 'annotation',
                            params: { annotationId: p.annotationId, fieldName: p.fieldName, fieldValues: p.fieldValues },
                        },
                    });
                }
            }
        }
    });
    return inlineTooltips;
}
/** Collect inline labels from all nodes in `tree`. */
function collectInlineLabels(tree, context) {
    const inlineLabels = [];
    (0, tree_utils_1.dfs)(tree, (node, parent) => {
        if (node.kind === 'label') {
            if ((parent === null || parent === void 0 ? void 0 : parent.kind) === 'component') {
                inlineLabels.push({
                    text: node.params.text,
                    position: {
                        name: 'selection',
                        params: {
                            selector: componentPropsFromSelector(parent.params.selector),
                        },
                    },
                });
            }
            else if ((parent === null || parent === void 0 ? void 0 : parent.kind) === 'component_from_uri' || (parent === null || parent === void 0 ? void 0 : parent.kind) === 'component_from_source') {
                const p = componentFromXProps(parent, context);
                if ((0, utils_1.isDefined)(p.annotationId) && (0, utils_1.isDefined)(p.fieldName) && (0, utils_1.isDefined)(p.fieldValues)) {
                    inlineLabels.push({
                        text: node.params.text,
                        position: {
                            name: 'selection',
                            params: {
                                selector: {
                                    name: 'annotation',
                                    params: { annotationId: p.annotationId, fieldName: p.fieldName, fieldValues: p.fieldValues },
                                },
                            },
                        },
                    });
                }
            }
        }
    });
    return inlineLabels;
}
/** Return `true` for components nodes which only serve for tooltip placement (not to be created in the MolStar object hierarchy) */
function isPhantomComponent(node) {
    if (node.ref !== undefined)
        return false;
    if (node.custom !== undefined && Object.keys(node.custom).length > 0)
        return false;
    return node.children && node.children.every(child => child.kind === 'tooltip' || child.kind === 'label');
    // These nodes could theoretically be removed when converting MVS to Molstar tree, but would get very tricky if we allow nested components
}
/** Create props for `StructureFromModel` transformer from a structure node. */
function structureProps(node) {
    var _a;
    const params = node.params;
    switch (params.type) {
        case 'model':
            return {
                type: {
                    name: 'model',
                    params: {}
                },
            };
        case 'assembly':
            return {
                type: {
                    name: 'assembly',
                    params: { id: (_a = params.assembly_id) !== null && _a !== void 0 ? _a : undefined }
                },
            };
        case 'symmetry':
            return {
                type: {
                    name: 'symmetry',
                    params: { ijkMin: linear_algebra_1.Vec3.ofArray(params.ijk_min), ijkMax: linear_algebra_1.Vec3.ofArray(params.ijk_max) }
                },
            };
        case 'symmetry_mates':
            return {
                type: {
                    name: 'symmetry-mates',
                    params: { radius: params.radius }
                }
            };
        default:
            throw new Error(`NotImplementedError: Loading action for "structure" node, type "${params.type}"`);
    }
}
/** Create value for `type` prop for `StructureComponent` transformer based on a MVS selector. */
function componentPropsFromSelector(selector) {
    if (selector === undefined) {
        return selector_1.SelectorAll;
    }
    else if (typeof selector === 'string') {
        return { name: 'static', params: selector };
    }
    else if (Array.isArray(selector)) {
        return { name: 'expression', params: (0, selections_1.rowsToExpression)(selector) };
    }
    else {
        return { name: 'expression', params: (0, selections_1.rowToExpression)(selector) };
    }
}
/** Return a pretty name for a value of selector param, e.g.  "protein" -> 'Protein', {label_asym_id: "A"} -> 'Custom Selection: {label_asym_id: "A"}' */
function prettyNameFromSelector(selector) {
    if (selector === undefined) {
        return 'All';
    }
    else if (typeof selector === 'string') {
        return (0, string_1.stringToWords)(selector);
    }
    else if (Array.isArray(selector)) {
        return `Custom Selection: [${selector.map(tree_utils_1.formatObject).join(', ')}]`;
    }
    else {
        return `Custom Selection: ${(0, tree_utils_1.formatObject)(selector)}`;
    }
}
/** Create props for `StructureRepresentation3D` transformer from a label_from_* node. */
function labelFromXProps(node, context) {
    var _a;
    const annotationId = context.annotationMap.get(node);
    const fieldName = node.params.field_name;
    const nearestReprNode = (_a = context.nearestReprMap) === null || _a === void 0 ? void 0 : _a.get(node);
    return {
        type: { name: representation_1.MVSAnnotationLabelRepresentationProvider.name, params: { annotationId, fieldName } },
        colorTheme: colorThemeForNode(nearestReprNode, context),
    };
}
/** Create props for `AnnotationStructureComponent` transformer from a component_from_* node. */
function componentFromXProps(node, context) {
    const annotationId = context.annotationMap.get(node);
    const { field_name, field_values } = node.params;
    return {
        annotationId,
        fieldName: field_name,
        fieldValues: field_values ? { name: 'selected', params: field_values.map(v => ({ value: v })) } : { name: 'all', params: {} },
        nullIfEmpty: false,
    };
}
/** Create props for `StructureRepresentation3D` transformer from a representation node. */
function representationProps(node) {
    var _a, _b;
    const alpha = alphaForNode(node);
    const params = node.params;
    switch (params.type) {
        case 'cartoon':
            return {
                type: { name: 'cartoon', params: { alpha, tubularHelices: params.tubular_helices } },
                sizeTheme: { name: 'uniform', params: { value: params.size_factor } },
            };
        case 'ball_and_stick':
            return {
                type: { name: 'ball-and-stick', params: { sizeFactor: ((_a = params.size_factor) !== null && _a !== void 0 ? _a : 1) * 0.5, sizeAspectRatio: 0.5, alpha, ignoreHydrogens: params.ignore_hydrogens } },
            };
        case 'spacefill':
            return {
                type: { name: 'spacefill', params: { alpha, ignoreHydrogens: params.ignore_hydrogens } },
                sizeTheme: { name: 'physical', params: { scale: params.size_factor } },
            };
        case 'carbohydrate':
            return {
                type: { name: 'carbohydrate', params: { alpha, sizeFactor: (_b = params.size_factor) !== null && _b !== void 0 ? _b : 1 } },
            };
        case 'surface':
            return {
                type: { name: 'molecular-surface', params: { alpha, ignoreHydrogens: params.ignore_hydrogens } },
                sizeTheme: { name: 'physical', params: { scale: params.size_factor } },
            };
        default:
            throw new Error('NotImplementedError');
    }
}
/** Create value for `type.params.alpha` prop for `StructureRepresentation3D` transformer from a representation node based on 'opacity' nodes in its subtree. */
function alphaForNode(node) {
    const children = (0, tree_schema_1.getChildren)(node).filter(c => c.kind === 'opacity');
    if (children.length > 0) {
        return children[children.length - 1].params.opacity;
    }
    else {
        return 1;
    }
}
function hasMolStarUseDefaultColoring(node) {
    if (!node.custom)
        return false;
    return 'molstar_use_default_coloring' in node.custom || 'molstar_color_theme_name' in node.custom;
}
/** Create value for `colorTheme` prop for `StructureRepresentation3D` transformer from a representation node based on color* nodes in its subtree. */
function colorThemeForNode(node, context) {
    var _a, _b, _c;
    if ((node === null || node === void 0 ? void 0 : node.kind) === 'representation') {
        const children = (0, tree_schema_1.getChildren)(node).filter(c => c.kind === 'color' || c.kind === 'color_from_uri' || c.kind === 'color_from_source');
        if (children.length === 0) {
            return {
                name: 'uniform',
                params: { value: (0, utils_1.decodeColor)(mvs_tree_1.DefaultColor) },
            };
        }
        else if (children.length === 1 && hasMolStarUseDefaultColoring(children[0])) {
            if ((_a = children[0].custom) === null || _a === void 0 ? void 0 : _a.molstar_use_default_coloring)
                return undefined;
            const custom = children[0].custom;
            return {
                name: (_b = custom === null || custom === void 0 ? void 0 : custom.molstar_color_theme_name) !== null && _b !== void 0 ? _b : undefined,
                params: (_c = custom === null || custom === void 0 ? void 0 : custom.molstar_color_theme_params) !== null && _c !== void 0 ? _c : {},
            };
        }
        else if (children.length === 1 && appliesColorToWholeRepr(children[0])) {
            return colorThemeForNode(children[0], context);
        }
        else {
            const layers = children.map(c => {
                const theme = colorThemeForNode(c, context);
                if (!theme)
                    return undefined;
                return { theme, selection: componentPropsFromSelector(c.kind === 'color' ? c.params.selector : undefined) };
            }).filter(t => !!t);
            return {
                name: multilayer_color_theme_1.MultilayerColorThemeName,
                params: { layers },
            };
        }
    }
    let annotationId = undefined;
    let fieldName = undefined;
    let color = undefined;
    switch (node === null || node === void 0 ? void 0 : node.kind) {
        case 'color_from_uri':
        case 'color_from_source':
            annotationId = context.annotationMap.get(node);
            fieldName = node.params.field_name;
            break;
        case 'color':
            color = node.params.color;
            break;
    }
    if (annotationId) {
        return {
            name: annotation_color_theme_1.MVSAnnotationColorThemeProvider.name,
            params: { annotationId, fieldName, background: multilayer_color_theme_1.NoColor },
        };
    }
    else {
        return {
            name: 'uniform',
            params: { value: (0, utils_1.decodeColor)(color) },
        };
    }
}
function appliesColorToWholeRepr(node) {
    if (node.kind === 'color') {
        return !(0, utils_1.isDefined)(node.params.selector) || node.params.selector === 'all';
    }
    else {
        return true;
    }
}
/** Create a mapping of nearest representation nodes for each node in the tree
 * (to transfer coloring to label nodes smartly).
 * Only considers nodes within the same 'structure' subtree. */
function makeNearestReprMap(root) {
    const map = new Map();
    // Propagate up:
    (0, tree_utils_1.dfs)(root, undefined, (node, parent) => {
        if (node.kind === 'representation') {
            map.set(node, node);
        }
        if (node.kind !== 'structure' && map.has(node) && parent && !map.has(parent)) { // do not propagate above the lowest structure node
            map.set(parent, map.get(node));
        }
    });
    // Propagate down:
    (0, tree_utils_1.dfs)(root, (node, parent) => {
        if (!map.has(node) && parent && map.has(parent)) {
            map.set(node, map.get(parent));
        }
    });
    return map;
}
/** Create props for `VolumeRepresentation3D` transformer from a representation node. */
function volumeRepresentationProps(node) {
    var _a;
    const alpha = alphaForNode(node);
    const params = node.params;
    switch (params.type) {
        case 'isosurface':
            const isoValue = typeof params.absolute_isovalue === 'number' ? volume_1.Volume.IsoValue.absolute(params.absolute_isovalue) : volume_1.Volume.IsoValue.relative((_a = params.relative_isovalue) !== null && _a !== void 0 ? _a : 0);
            const visuals = [];
            if (params.show_wireframe)
                visuals.push('wireframe');
            if (params.show_faces)
                visuals.push('solid');
            return {
                type: { name: 'isosurface', params: { alpha, isoValue, visuals } },
            };
        default:
            throw new Error('NotImplementedError');
    }
}
/** Create value for `colorTheme` prop for `StructureRepresentation3D` transformer from a representation node based on color* nodes in its subtree. */
function volumeColorThemeForNode(node, context) {
    if ((node === null || node === void 0 ? void 0 : node.kind) !== 'volume_representation')
        return undefined;
    const children = (0, tree_schema_1.getChildren)(node).filter(c => c.kind === 'color');
    if (children.length === 0) {
        return {
            name: 'uniform',
            params: { value: (0, utils_1.decodeColor)(mvs_tree_1.DefaultColor) },
        };
    }
    if (children.length === 1) {
        return colorThemeForNode(children[0], context);
    }
}
