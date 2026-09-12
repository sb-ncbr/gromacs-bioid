import { jsx as _jsx, Fragment as _Fragment, jsxs as _jsxs } from "react/jsx-runtime";
/**
 * Copyright (c) 2022-2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 * @author David Sehnal <david.sehnal@gmail.com>
 * @author Adam Midlik <midlik@gmail.com>
 */
import { PostprocessingParams } from '../../mol-canvas3d/passes/postprocessing';
import { PresetStructureRepresentations } from '../../mol-plugin-state/builder/structure/representation-preset';
import { PluginConfig } from '../../mol-plugin/config';
import { Color } from '../../mol-util/color';
import { ParamDefinition as PD } from '../../mol-util/param-definition';
import { CollapsableControls, PurePluginUIComponent } from '../base';
import { Button } from '../controls/common';
import { MagicWandSvg } from '../controls/icons';
export class StructureQuickStylesControls extends CollapsableControls {
    defaultState() {
        return {
            isCollapsed: false,
            header: 'Quick Styles',
            brand: { accent: 'gray', svg: MagicWandSvg }
        };
    }
    renderControls() {
        return _jsx(_Fragment, { children: _jsx(QuickStyles, {}) });
    }
}
export class QuickStyles extends PurePluginUIComponent {
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
        return _jsxs(_Fragment, { children: [_jsx(NoncollapsableGroup, { title: 'Apply Representation', children: _jsxs("div", { className: 'msp-flex-row', children: [_jsx(Button, { title: 'Applies default representation preset (depends on structure size)', onClick: () => this.applyRepresentation('default'), disabled: this.state.busy, children: "Default" }), _jsx(Button, { title: 'Applies cartoon polymer and ball-and-stick ligand representation preset', onClick: () => this.applyRepresentation('cartoon'), disabled: this.state.busy, children: "Cartoon" }), _jsx(Button, { title: 'Applies spacefill representation preset', onClick: () => this.applyRepresentation('spacefill'), disabled: this.state.busy, children: "Spacefill" }), _jsx(Button, { title: 'Applies molecular surface representation preset', onClick: () => this.applyRepresentation('surface'), disabled: this.state.busy, children: "Surface" })] }) }), _jsx(NoncollapsableGroup, { title: 'Apply Style', children: _jsxs("div", { className: 'msp-flex-row', children: [_jsx(Button, { title: 'Applies default appearance (no outline, no ignore-light)', onClick: () => this.applyStyle('default'), disabled: this.state.busy, children: "Default" }), _jsx(Button, { title: 'Applies illustrative appearance (outline, ignore-light)', onClick: () => this.applyStyle('illustrative'), disabled: this.state.busy, children: "Illustrative" })] }) })] });
    }
}
/** Visually imitates `ControlGroup` but is always expanded */
function NoncollapsableGroup(props) {
    return _jsxs("div", { className: 'msp-control-group-wrapper', children: [_jsx("div", { className: 'msp-control-group-header', children: _jsx("div", { children: _jsx("b", { children: props.title }) }) }), props.children] });
}
async function applyRepresentationPreset(plugin, preset) {
    const { structures } = plugin.managers.structure.hierarchy.selection;
    switch (preset) {
        case 'default':
            const defaultPreset = plugin.config.get(PluginConfig.Structure.DefaultRepresentationPreset) || PresetStructureRepresentations.auto.id;
            const provider = plugin.builders.structure.representation.resolveProvider(defaultPreset);
            await plugin.managers.structure.component.applyPreset(structures, provider);
            break;
        case 'spacefill':
            await plugin.managers.structure.component.applyPreset(structures, PresetStructureRepresentations.illustrative);
            break;
        case 'cartoon':
            await plugin.managers.structure.component.applyPreset(structures, PresetStructureRepresentations['polymer-and-ligand']);
            break;
        case 'surface':
            await plugin.managers.structure.component.applyPreset(structures, PresetStructureRepresentations['molecular-surface']);
            break;
    }
}
async function applyStyle(plugin, style) {
    if (style === 'default') {
        await plugin.managers.structure.component.setOptions({ ...plugin.managers.structure.component.state.options, ignoreLight: false });
        if (plugin.canvas3d) {
            const p = PD.getDefaultValues(PostprocessingParams);
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
                                color: Color(0x000000),
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
                                color: Color(0x000000),
                                transparentThreshold: 0.4,
                            }
                    },
                    shadow: { name: 'off', params: {} },
                }
            });
        }
    }
}
