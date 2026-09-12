"use strict";
/**
 * Copyright (c) 2021-2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.VolumeValueColorThemeProvider = exports.VolumeValueColorThemeParams = void 0;
exports.getVolumeValueColorThemeParams = getVolumeValueColorThemeParams;
exports.VolumeValueColorTheme = VolumeValueColorTheme;
const color_1 = require("../color");
const param_definition_1 = require("../../mol-util/param-definition");
const names_1 = require("../../mol-util/color/names");
const volume_1 = require("../../mol-model/volume/volume");
const categories_1 = require("./categories");
const interpolate_1 = require("../../mol-math/interpolate");
const color_2 = require("../../mol-util/color/color");
const grid_1 = require("../../mol-model/volume/grid");
const location_iterator_1 = require("../../mol-geo/util/location-iterator");
const Description = 'Assign color based on the given value of a volume cell.';
exports.VolumeValueColorThemeParams = {
    colorList: param_definition_1.ParamDefinition.ColorList({
        kind: 'interpolate',
        colors: [
            [names_1.ColorNames.white, 0],
            [names_1.ColorNames.red, 0.25],
            [names_1.ColorNames.white, 0.5],
            [names_1.ColorNames.blue, 0.75],
            [names_1.ColorNames.white, 1]
        ]
    }, { offsets: true, isEssential: true }),
    domain: param_definition_1.ParamDefinition.MappedStatic('auto', {
        custom: param_definition_1.ParamDefinition.Interval([-1, 1], { step: 0.001 }),
        auto: param_definition_1.ParamDefinition.Group({
            symmetric: param_definition_1.ParamDefinition.Boolean(false, { description: 'If true the automatic range is determined as [-|max|, |max|].' })
        })
    }),
    isRelative: param_definition_1.ParamDefinition.Boolean(false, { description: 'If true the value is treated as relative to the volume mean and sigma.' }),
    defaultColor: param_definition_1.ParamDefinition.Color((0, color_2.Color)(0xcccccc)),
};
function getVolumeValueColorThemeParams(ctx) {
    return exports.VolumeValueColorThemeParams; // TODO return copy
}
function VolumeValueColorTheme(ctx, props) {
    var _a;
    if (ctx.volume) {
        const { min, max, mean, sigma } = ctx.volume.grid.stats;
        const domain = props.domain.name === 'custom' ? props.domain.params : [min, max];
        const { colorList, defaultColor } = props;
        if (props.domain.name === 'auto' && props.isRelative) {
            domain[0] = (domain[0] - mean) / sigma;
            domain[1] = (domain[1] - mean) / sigma;
        }
        if (props.domain.name === 'auto' && props.domain.params.symmetric) {
            const max = Math.max(Math.abs(domain[0]), Math.abs(domain[1]));
            domain[0] = -max;
            domain[1] = max;
        }
        if ((_a = ctx.locationKinds) === null || _a === void 0 ? void 0 : _a.includes('direct-location')) {
            // this is for direct-volume rendering where the location is the volume grid cell
            // and we only need to provide the domain and palette here
            const normalizedDomain = [
                (0, interpolate_1.normalize)(domain[0], min, max),
                (0, interpolate_1.normalize)(domain[1], min, max)
            ];
            const palette = color_1.ColorTheme.Palette(colorList.colors, colorList.kind, normalizedDomain, defaultColor);
            return {
                factory: VolumeValueColorTheme,
                granularity: 'direct',
                props,
                description: Description,
                palette,
            };
        }
        else {
            const getTrilinearlyInterpolated = grid_1.Grid.makeGetTrilinearlyInterpolated(ctx.volume.grid, 'none');
            const color = (location) => {
                if (!(0, location_iterator_1.isPositionLocation)(location)) {
                    return props.defaultColor;
                }
                const value = getTrilinearlyInterpolated(location.position);
                if (isNaN(value))
                    return props.defaultColor;
                return ((0, interpolate_1.clamp)((value - domain[0]) / (domain[1] - domain[0]), 0, 1) * color_1.ColorTheme.PaletteScale);
            };
            const palette = color_1.ColorTheme.Palette(colorList.colors, colorList.kind, undefined, defaultColor);
            return {
                factory: VolumeValueColorTheme,
                granularity: 'vertex',
                preferSmoothing: true,
                color,
                palette,
                props,
                description: Description,
            };
        }
    }
    else {
        return {
            factory: VolumeValueColorTheme,
            granularity: 'uniform',
            color: () => props.defaultColor,
            props,
            description: Description,
        };
    }
}
exports.VolumeValueColorThemeProvider = {
    name: 'volume-value',
    label: 'Volume Value',
    category: categories_1.ColorThemeCategory.Misc,
    factory: VolumeValueColorTheme,
    getParams: getVolumeValueColorThemeParams,
    defaultValues: param_definition_1.ParamDefinition.getDefaultValues(exports.VolumeValueColorThemeParams),
    isApplicable: (ctx) => !!ctx.volume && !volume_1.Volume.Segmentation.get(ctx.volume),
};
