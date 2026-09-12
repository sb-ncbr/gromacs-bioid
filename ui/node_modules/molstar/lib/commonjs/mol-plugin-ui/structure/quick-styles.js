"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.QuickStyles = exports.StructureQuickStylesControls = void 0;
const jsx_runtime_1 = require("react/jsx-runtime");
/**
 * Copyright (c) 2022-2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 * @author David Sehnal <david.sehnal@gmail.com>
 * @author Adam Midlik <midlik@gmail.com>
 */
const postprocessing_1 = require("../../mol-canvas3d/passes/postprocessing");
const representation_preset_1 = require("../../mol-plugin-state/builder/structure/representation-preset");
const config_1 = require("../../mol-plugin/config");
const color_1 = require("../../mol-util/color");
const param_definition_1 = require("../../mol-util/param-definition");
const base_1 = require("../base");
const common_1 = require("../controls/common");
const icons_1 = require("../controls/icons");
class StructureQuickStylesControls extends base_1.CollapsableControls {
    defaultState() {
        return {
            isCollapsed: false,
            header: 'Quick Styles',
            brand: { accent: 'gray', svg: icons_1.MagicWandSvg }
        };
    }
    renderControls() {
        return (0, jsx_runtime_1.jsx)(jsx_runtime_1.Fragment, { children: (0, jsx_runtime_1.jsx)(QuickStyles, {}) });
    }
}
exports.StructureQuickStylesControls = StructureQuickStylesControls;
class QuickStyles extends base_1.PurePluginUIComponent {
    constructor() {
        super(...arguments);
        this.state = { busy: false, style: 'default' };
    }
    async applyRepresentation(preset) {
        this.setState({ busy: true });
        await applyRepresentationPreset(this.plugin, preset);
        await applyStyle(this.plugin, this.state.style); // reapplying current style is desired because some presets come with weird params (namely spacefill comes with ignoreLight:true)
        this.setState({ busy: false });
    }
    async applyStyle(style) {
        this.setState({ busy: true });
        await applyStyle(this.plugin, style);
        this.setState({ busy: false, style });
    }
    render() {
        return (0, jsx_runtime_1.jsxs)(jsx_runtime_1.Fragment, { children: [(0, jsx_runtime_1.jsx)(NoncollapsableGroup, { title: 'Apply Representation', children: (0, jsx_runtime_1.jsxs)("div", { className: 'msp-flex-row', children: [(0, jsx_runtime_1.jsx)(common_1.Button, { title: 'Applies default representation preset (depends on structure size)', onClick: () => this.applyRepresentation('default'), disabled: this.state.busy, children: "Default" }), (0, jsx_runtime_1.jsx)(common_1.Button, { title: 'Applies cartoon polymer and ball-and-stick ligand representation preset', onClick: () => this.applyRepresentation('cartoon'), disabled: this.state.busy, children: "Cartoon" }), (0, jsx_runtime_1.jsx)(common_1.Button, { title: 'Applies spacefill representation preset', onClick: () => this.applyRepresentation('spacefill'), disabled: this.state.busy, children: "Spacefill" }), (0, jsx_runtime_1.jsx)(common_1.Button, { title: 'Applies molecular surface representation preset', onClick: () => this.applyRepresentation('surface'), disabled: this.state.busy, children: "Surface" })] }) }), (0, jsx_runtime_1.jsx)(NoncollapsableGroup, { title: 'Apply Style', children: (0, jsx_runtime_1.jsxs)("div", { className: 'msp-flex-row', children: [(0, jsx_runtime_1.jsx)(common_1.Button, { title: 'Applies default appearance (no outline, no ignore-light)', onClick: () => this.applyStyle('default'), disabled: this.state.busy, children: "Default" }), (0, jsx_runtime_1.jsx)(common_1.Button, { title: 'Applies illustrative appearance (outline, ignore-light)', onClick: () => this.applyStyle('illustrative'), disabled: this.state.busy, children: "Illustrative" })] }) })] });
    }
}
exports.QuickStyles = QuickStyles;
/** Visually imitates `ControlGroup` but is always expanded */
function NoncollapsableGroup(props) {
    return (0, jsx_runtime_1.jsxs)("div", { className: 'msp-control-group-wrapper', children: [(0, jsx_runtime_1.jsx)("div", { className: 'msp-control-group-header', children: (0, jsx_runtime_1.jsx)("div", { children: (0, jsx_runtime_1.jsx)("b", { children: props.title }) }) }), props.children] });
}
async function applyRepresentationPreset(plugin, preset) {
    const { structures } = plugin.managers.structure.hierarchy.selection;
    switch (preset) {
        case 'default':
            const defaultPreset = plugin.config.get(config_1.PluginConfig.Structure.DefaultRepresentationPreset) || representation_preset_1.PresetStructureRepresentations.auto.id;
            const provider = plugin.builders.structure.representation.resolveProvider(defaultPreset);
            await plugin.managers.structure.component.applyPreset(structures, provider);
            break;
        case 'spacefill':
            await plugin.managers.structure.component.applyPreset(structures, representation_preset_1.PresetStructureRepresentations.illustrative);
            break;
        case 'cartoon':
            await plugin.managers.structure.component.applyPreset(structures, representation_preset_1.PresetStructureRepresentations['polymer-and-ligand']);
            break;
        case 'surface':
            await plugin.managers.structure.component.applyPreset(structures, representation_preset_1.PresetStructureRepresentations['molecular-surface']);
            break;
    }
}
async function applyStyle(plugin, style) {
    if (style === 'default') {
        await plugin.managers.structure.component.setOptions({ ...plugin.managers.structure.component.state.options, ignoreLight: false });
        if (plugin.canvas3d) {
            const p = param_definition_1.ParamDefinition.getDefaultValues(postprocessing_1.PostprocessingParams);
            plugin.canvas3d.setProps({
                postprocessing: { outline: p.outline, occlusion: p.occlusion, shadow: p.shadow }
            });
        }
    }
    if (style === 'illustrative') {
        await plugin.managers.structure.component.setOptions({ ...plugin.managers.structure.component.state.options, ignoreLight: true });
        if (plugin.canvas3d) {
            const pp = plugin.canvas3d.props.postprocessing;
            plugin.canvas3d.setProps({
                postprocessing: {
                    outline: {
                        name: 'on',
                        params: pp.outline.name === 'on'
                            ? pp.outline.params
                            : {
                                scale: 1,
                                color: (0, color_1.Color)(0x000000),
                                threshold: 0.33,
                                includeTransparent: true,
                            }
                    },
                    occlusion: {
                        name: 'on',
                        params: pp.occlusion.name === 'on'
                            ? pp.occlusion.params
                            : {
                                multiScale: { name: 'off', params: {} },
                                radius: 5,
                                bias: 0.8,
                                blurKernelSize: 15,
                                blurDepthBias: 0.5,
                                samples: 32,
                                resolutionScale: 1,
                                color: (0, color_1.Color)(0x000000),
                                transparentThreshold: 0.4,
                            }
                    },
                    shadow: { name: 'off', params: {} },
                }
            });
        }
    }
}
