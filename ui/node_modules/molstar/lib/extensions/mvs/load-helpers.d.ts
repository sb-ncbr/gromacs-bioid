/**
 * Copyright (c) 2023-2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Adam Midlik <midlik@gmail.com>
 * @author David Sehnal <david.sehnal@gmail.com>
 */
import { Mat4 } from '../../mol-math/linear-algebra';
import { StructureComponentParams } from '../../mol-plugin-state/helpers/structure-component';
import { StructureFromModel, TransformStructureConformation } from '../../mol-plugin-state/transforms/model';
import { StructureRepresentation3D, VolumeRepresentation3D } from '../../mol-plugin-state/transforms/representation';
import { StateTransformer } from '../../mol-state';
import { MVSAnnotationSpec } from './components/annotation-prop';
import { MVSAnnotationStructureComponentProps } from './components/annotation-structure-component';
import { MVSAnnotationTooltipsProps } from './components/annotation-tooltips-prop';
import { CustomLabelTextProps } from './components/custom-label/visual';
import { CustomTooltipsProps } from './components/custom-tooltips-prop';
import { ElementOfSet } from './helpers/utils';
import { MolstarLoadingContext } from './load';
import { Subtree } from './tree/generic/tree-schema';
import { MolstarNode, MolstarNodeParams, MolstarSubtree, MolstarTree } from './tree/molstar/molstar-tree';
export declare const AnnotationFromUriKinds: Set<"component_from_uri" | "color_from_uri" | "label_from_uri" | "tooltip_from_uri">;
export type AnnotationFromUriKind = ElementOfSet<typeof AnnotationFromUriKinds>;
export declare const AnnotationFromSourceKinds: Set<"component_from_source" | "color_from_source" | "label_from_source" | "tooltip_from_source">;
export type AnnotationFromSourceKind = ElementOfSet<typeof AnnotationFromSourceKinds>;
/** Return a 4x4 matrix representing a rotation followed by a translation */
export declare function transformFromRotationTranslation(rotation: number[] | null | undefined, translation: number[] | null | undefined): Mat4;
/** Create an array of props for `TransformStructureConformation` transformers from all 'transform' nodes applied to a 'structure' node. */
export declare function transformProps(node: MolstarSubtree<'structure'>): StateTransformer.Params<TransformStructureConformation>[];
/** Collect distinct annotation specs from all nodes in `tree` and set `context.annotationMap[node]` to respective annotationIds */
export declare function collectAnnotationReferences(tree: Subtree<MolstarTree>, context: MolstarLoadingContext): MVSAnnotationSpec[];
/** Collect annotation tooltips from all nodes in `tree` and map them to annotationIds. */
export declare function collectAnnotationTooltips(tree: MolstarSubtree<'structure'>, context: MolstarLoadingContext): MVSAnnotationTooltipsProps['tooltips'];
/** Collect inline tooltips from all nodes in `tree`. */
export declare function collectInlineTooltips(tree: MolstarSubtree<'structure'>, context: MolstarLoadingContext): CustomTooltipsProps['tooltips'];
/** Collect inline labels from all nodes in `tree`. */
export declare function collectInlineLabels(tree: MolstarSubtree<'structure'>, context: MolstarLoadingContext): CustomLabelTextProps['items'];
/** Return `true` for components nodes which only serve for tooltip placement (not to be created in the MolStar object hierarchy) */
export declare function isPhantomComponent(node: MolstarSubtree<'component' | 'component_from_uri' | 'component_from_source'>): boolean | undefined;
/** Create props for `StructureFromModel` transformer from a structure node. */
export declare function structureProps(node: MolstarNode<'structure'>): StateTransformer.Params<StructureFromModel>;
/** Create value for `type` prop for `StructureComponent` transformer based on a MVS selector. */
export declare function componentPropsFromSelector(selector?: MolstarNodeParams<'component'>['selector']): StructureComponentParams['type'];
/** Return a pretty name for a value of selector param, e.g.  "protein" -> 'Protein', {label_asym_id: "A"} -> 'Custom Selection: {label_asym_id: "A"}' */
export declare function prettyNameFromSelector(selector?: MolstarNodeParams<'component'>['selector']): string;
/** Create props for `StructureRepresentation3D` transformer from a label_from_* node. */
export declare function labelFromXProps(node: MolstarNode<'label_from_uri' | 'label_from_source'>, context: MolstarLoadingContext): Partial<StateTransformer.Params<StructureRepresentation3D>>;
/** Create props for `AnnotationStructureComponent` transformer from a component_from_* node. */
export declare function componentFromXProps(node: MolstarNode<'component_from_uri' | 'component_from_source'>, context: MolstarLoadingContext): Partial<MVSAnnotationStructureComponentProps>;
/** Create props for `StructureRepresentation3D` transformer from a representation node. */
export declare function representationProps(node: MolstarSubtree<'representation'>): Partial<StateTransformer.Params<StructureRepresentation3D>>;
/** Create value for `type.params.alpha` prop for `StructureRepresentation3D` transformer from a representation node based on 'opacity' nodes in its subtree. */
export declare function alphaForNode(node: MolstarSubtree<'representation' | 'volume_representation'>): number;
/** Create value for `colorTheme` prop for `StructureRepresentation3D` transformer from a representation node based on color* nodes in its subtree. */
export declare function colorThemeForNode(node: MolstarSubtree<'color' | 'color_from_uri' | 'color_from_source' | 'representation'> | undefined, context: MolstarLoadingContext): StateTransformer.Params<StructureRepresentation3D>['colorTheme'] | undefined;
/** Create a mapping of nearest representation nodes for each node in the tree
 * (to transfer coloring to label nodes smartly).
 * Only considers nodes within the same 'structure' subtree. */
export declare function makeNearestReprMap(root: MolstarTree): Map<MolstarNode, {
    kind: "representation";
    params: ({
        type: "carbohydrate";
    } & {
        size_factor: number;
    } & {}) | ({
        type: "spacefill";
    } & {
        size_factor: number;
        ignore_hydrogens: boolean;
    } & {}) | ({
        type: "surface";
    } & {
        size_factor: number;
        ignore_hydrogens: boolean;
    } & {}) | ({
        type: "cartoon";
    } & {
        size_factor: number;
        tubular_helices: boolean;
    } & {}) | ({
        type: "ball_and_stick";
    } & {
        size_factor: number;
        ignore_hydrogens: boolean;
    } & {});
    custom?: import("./tree/generic/tree-schema").CustomProps;
    ref?: string;
}>;
/** Create props for `VolumeRepresentation3D` transformer from a representation node. */
export declare function volumeRepresentationProps(node: MolstarSubtree<'volume_representation'>): Partial<StateTransformer.Params<VolumeRepresentation3D>>;
/** Create value for `colorTheme` prop for `StructureRepresentation3D` transformer from a representation node based on color* nodes in its subtree. */
export declare function volumeColorThemeForNode(node: MolstarSubtree<'volume_representation'> | undefined, context: MolstarLoadingContext): StateTransformer.Params<VolumeRepresentation3D>['colorTheme'] | undefined;
