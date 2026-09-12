/**
 * Copyright (c) 2019-2022 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
import { PluginBehavior } from '../../../behavior';
import { ParamDefinition as PD } from '../../../../mol-util/param-definition';
import { PluginContext } from '../../../context';
import { Clip } from '../../../../mol-util/clip';
declare const StructureFocusRepresentationParams: (plugin: PluginContext) => {
    expandRadius: PD.Numeric;
    targetParams: PD.Group<PD.Normalize<{
        [x: string]: /*elided*/ any;
    }>>;
    surroundingsParams: PD.Group<PD.Normalize<{
        [x: string]: /*elided*/ any;
    }>>;
    nciParams: PD.Group<PD.Normalize<{
        [x: string]: /*elided*/ any;
    }>>;
    components: PD.MultiSelect<"target" | "surroundings" | "interactions">;
    excludeTargetFromSurroundings: PD.BooleanParam;
    ignoreHydrogens: PD.BooleanParam;
    ignoreHydrogensVariant: PD.Select<"all" | "non-polar">;
    ignoreLight: PD.BooleanParam;
    material: PD.Group<PD.Normalize<{
        metalness: number;
        roughness: number;
        bumpiness: number;
    }>>;
    clip: PD.Group<PD.Normalize<{
        variant: Clip.Variant;
        objects: PD.Normalize<{
            type: /*elided*/ any;
            invert: /*elided*/ any;
            position: /*elided*/ any;
            rotation: /*elided*/ any;
            scale: /*elided*/ any;
            transform: /*elided*/ any;
        }>[];
    }>>;
};
type StructureFocusRepresentationProps = PD.ValuesFor<ReturnType<typeof StructureFocusRepresentationParams>>;
export declare enum StructureFocusRepresentationTags {
    TargetSel = "structure-focus-target-sel",
    TargetRepr = "structure-focus-target-repr",
    SurrSel = "structure-focus-surr-sel",
    SurrRepr = "structure-focus-surr-repr",
    SurrNciRepr = "structure-focus-surr-nci-repr"
}
export declare const StructureFocusRepresentation: import("../../../../mol-state").StateTransformer<PluginBehavior.Category, PluginBehavior.Behavior, StructureFocusRepresentationProps>;
export {};
