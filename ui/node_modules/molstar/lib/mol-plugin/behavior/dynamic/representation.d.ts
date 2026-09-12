/**
 * Copyright (c) 2018-2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 * @author Jason Pattle <jpattle.exscientia.co.uk>
 * @author Adam Midlik <midlik@gmail.com>
 */
import { PluginBehavior } from '../behavior';
import { Binding } from '../../../mol-util/binding';
import { ParamDefinition as PD } from '../../../mol-util/param-definition';
export declare const HighlightLoci: import("../../../mol-state").StateTransformer<PluginBehavior.Category, PluginBehavior.Behavior, PD.Values<{
    bindings: PD.Value<{
        hoverHighlightOnly: Binding;
        hoverHighlightOnlyExtend: Binding;
    }>;
    ignore: PD.Value<("element-loci" | "structure-loci" | "bond-loci" | "volume-loci" | "isosurface-loci" | "cell-loci" | "segment-loci" | "every-loci" | "empty-loci" | "data-loci" | "shape-loci" | "group-loci")[]>;
    preferAtoms: PD.BooleanParam;
    mark: PD.BooleanParam;
}>>;
export declare const DefaultSelectLociBindings: {
    clickSelect: Binding;
    clickSelectOnly: Binding;
    clickToggle: Binding;
    clickToggleExtend: Binding;
    clickDeselect: Binding;
    clickDeselectAllOnEmpty: Binding;
};
export declare const SelectLoci: import("../../../mol-state").StateTransformer<PluginBehavior.Category, PluginBehavior.Behavior, PD.Values<{
    bindings: PD.Value<{
        clickSelect: Binding;
        clickSelectOnly: Binding;
        clickToggle: Binding;
        clickToggleExtend: Binding;
        clickDeselect: Binding;
        clickDeselectAllOnEmpty: Binding;
    }>;
    ignore: PD.Value<("element-loci" | "structure-loci" | "bond-loci" | "volume-loci" | "isosurface-loci" | "cell-loci" | "segment-loci" | "every-loci" | "empty-loci" | "data-loci" | "shape-loci" | "group-loci")[]>;
    preferAtoms: PD.BooleanParam;
    mark: PD.BooleanParam;
}>>;
export declare const DefaultLociLabelProvider: import("../../../mol-state").StateTransformer<PluginBehavior.Category, PluginBehavior.Behavior, {}>;
export declare const DefaultFocusLociBindings: {
    clickFocus: Binding;
    clickFocusAdd: Binding;
    clickFocusExtend: Binding;
    clickFocusSelectMode: Binding;
    clickFocusAddSelectMode: Binding;
    clickFocusExtendSelectMode: Binding;
};
export declare const FocusLoci: import("../../../mol-state").StateTransformer<PluginBehavior.Category, PluginBehavior.Behavior, PD.Values<{
    bindings: PD.Value<{
        clickFocus: Binding;
        clickFocusAdd: Binding;
        clickFocusExtend: Binding;
        clickFocusSelectMode: Binding;
        clickFocusAddSelectMode: Binding;
        clickFocusExtendSelectMode: Binding;
    }>;
}>>;
