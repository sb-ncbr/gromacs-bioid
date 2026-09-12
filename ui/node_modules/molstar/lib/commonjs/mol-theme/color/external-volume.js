"use strict";
/**
 * Copyright (c) 2024-2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 * @author Cai Huiyu <szmun.caihy@gmail.com>
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.ExternalVolumeColorThemeProvider = exports.ExternalVolumeColorThemeParams = void 0;
exports.ExternalVolumeColorTheme = ExternalVolumeColorTheme;
const color_1 = require("../../mol-util/color");
const color_2 = require("../color");
const param_definition_1 = require("../../mol-util/param-definition");
const volume_1 = require("../../mol-model/volume");
const location_iterator_1 = require("../../mol-geo/util/location-iterator");
const linear_algebra_1 = require("../../mol-math/linear-algebra");
const interpolate_1 = require("../../mol-math/interpolate");
const categories_1 = require("./categories");
const Description = `Assigns a color based on volume value at a given vertex.`;
exports.ExternalVolumeColorThemeParams = {
    volume: param_definition_1.ParamDefinition.ValueRef((ctx) => {
        const volumes = ctx.state.data.selectQ(q => q.root.subtree().filter(c => { var _a; return volume_1.Volume.is((_a = c.obj) === null || _a === void 0 ? void 0 : _a.data); }));
        return volumes.map(v => { var _a, _b; return [v.transform.ref, (_b = (_a = v.obj) === null || _a === void 0 ? void 0 : _a.label) !== null && _b !== void 0 ? _b : '<unknown>']; });
    }, (ref, getData) => getData(ref)),
    coloring: param_definition_1.ParamDefinition.MappedStatic('absolute-value', {
        'absolute-value': param_definition_1.ParamDefinition.Group({
            domain: param_definition_1.ParamDefinition.MappedStatic('auto', {
                custom: param_definition_1.ParamDefinition.Interval([-1, 1], { step: 0.001 }),
                auto: param_definition_1.ParamDefinition.Group({
                    symmetric: param_definition_1.ParamDefinition.Boolean(false, { description: 'If true the automatic range is determined as [-|max|, |max|].' })
                })
            }),
            list: param_definition_1.ParamDefinition.ColorList('red-white-blue', { presetKind: 'scale' })
        }),
        'relative-value': param_definition_1.ParamDefinition.Group({
            domain: param_definition_1.ParamDefinition.MappedStatic('auto', {
                custom: param_definition_1.ParamDefinition.Interval([-1, 1], { step: 0.001 }),
                auto: param_definition_1.ParamDefinition.Group({
                    symmetric: param_definition_1.ParamDefinition.Boolean(false, { description: 'If true the automatic range is determined as [-|max|, |max|].' })
                })
            }),
            list: param_definition_1.ParamDefinition.ColorList('red-white-blue', { presetKind: 'scale' })
        })
    }),
    defaultColor: param_definition_1.ParamDefinition.Color((0, color_1.Color)(0xcccccc)),
    normalOffset: param_definition_1.ParamDefinition.Numeric(0., { min: 0, max: 20, step: 0.1 }, { description: 'Offset vertex position along its normal by given amount.' }),
    usePalette: param_definition_1.ParamDefinition.Boolean(false, { description: 'Use a palette to color at the pixel level.' }),
};
function ExternalVolumeColorTheme(ctx, props) {
    let volume;
    try {
        volume = props.volume.getValue();
    }
    catch (_a) {
        // .getValue() is resolved during state reconciliation => would throw from UI
    }
    // NOTE: this will currently be slow for with GPU/texture meshes due to slow iteration
    // TODO: create texture to be able to do the sampling on the GPU
    let color;
    let palette;
    const { normalOffset, defaultColor, usePalette } = props;
    if (volume) {
        const coloring = props.coloring.params;
        const { stats } = volume.grid;
        const domain = coloring.domain.name === 'custom' ? coloring.domain.params : [stats.min, stats.max];
        const isRelative = props.coloring.name === 'relative-value';
        if (coloring.domain.name === 'auto' && isRelative) {
            domain[0] = (domain[0] - stats.mean) / stats.sigma;
            domain[1] = (domain[1] - stats.mean) / stats.sigma;
        }
        if (coloring.domain.name === 'auto' && coloring.domain.params.symmetric) {
            const max = Math.max(Math.abs(domain[0]), Math.abs(domain[1]));
            domain[0] = -max;
            domain[1] = max;
        }
        const scale = color_1.ColorScale.create({ domain, listOrName: coloring.list.colors });
        const position = (0, linear_algebra_1.Vec3)();
        const getTrilinearlyInterpolated = volume_1.Grid.makeGetTrilinearlyInterpolated(volume.grid, isRelative ? 'relative' : 'none');
        color = (location) => {
            if (!(0, location_iterator_1.isPositionLocation)(location)) {
                return defaultColor;
            }
            // Offset the vertex position along its normal
            if (normalOffset > 0) {
                linear_algebra_1.Vec3.scaleAndAdd(position, location.position, location.normal, normalOffset);
            }
            else {
                linear_algebra_1.Vec3.copy(position, location.position);
            }
            const value = getTrilinearlyInterpolated(position);
            if (isNaN(value))
                return defaultColor;
            if (usePalette) {
                return ((0, interpolate_1.clamp)((value - domain[0]) / (domain[1] - domain[0]), 0, 1) * color_2.ColorTheme.PaletteScale);
            }
            else {
                return scale.color(value);
            }
        };
        palette = usePalette ? {
            colors: coloring.list.colors.map(e => Array.isArray(e) ? e[0] : e),
            filter: (coloring.list.kind === 'set' ? 'nearest' : 'linear')
        } : undefined;
    }
    else {
        color = () => defaultColor;
    }
    return {
        factory: ExternalVolumeColorTheme,
        granularity: 'vertex',
        preferSmoothing: true,
        color,
        palette,
        props,
        description: Description,
        // TODO: figure out how to do legend for this
    };
}
exports.ExternalVolumeColorThemeProvider = {
    name: 'external-volume',
    label: 'External Volume',
    category: categories_1.ColorThemeCategory.Misc,
    factory: ExternalVolumeColorTheme,
    getParams: () => exports.ExternalVolumeColorThemeParams,
    defaultValues: param_definition_1.ParamDefinition.getDefaultValues(exports.ExternalVolumeColorThemeParams),
    isApplicable: (ctx) => true,
};
