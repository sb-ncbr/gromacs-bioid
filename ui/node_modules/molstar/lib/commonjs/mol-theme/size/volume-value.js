"use strict";
/**
 * Copyright (c) 2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.VolumeValueSizeThemeProvider = exports.VolumeValueSizeThemeParams = void 0;
exports.getVolumeValueSizeThemeParams = getVolumeValueSizeThemeParams;
exports.VolumeValueSizeTheme = VolumeValueSizeTheme;
const param_definition_1 = require("../../mol-util/param-definition");
const volume_1 = require("../../mol-model/volume/volume");
const Description = 'Assign size based on the given value of a volume cell.';
exports.VolumeValueSizeThemeParams = {
    scale: param_definition_1.ParamDefinition.Numeric(1, { min: 0.1, max: 5, step: 0.1 }),
};
function getVolumeValueSizeThemeParams(ctx) {
    return exports.VolumeValueSizeThemeParams; // TODO return copy
}
function VolumeValueSizeTheme(ctx, props) {
    if (ctx.volume) {
        const { data } = ctx.volume.grid.cells;
        const isLocation = volume_1.Volume.Cell.isLocation;
        const size = (location) => {
            if (isLocation(location)) {
                return data[location.cell] * props.scale;
            }
            else {
                return 0;
            }
        };
        return {
            factory: VolumeValueSizeTheme,
            granularity: 'group',
            size,
            props,
            description: Description
        };
    }
    else {
        return {
            factory: VolumeValueSizeTheme,
            granularity: 'uniform',
            size: () => props.scale,
            props,
            description: Description
        };
    }
}
exports.VolumeValueSizeThemeProvider = {
    name: 'volume-value',
    label: 'Volume Value',
    category: '',
    factory: VolumeValueSizeTheme,
    getParams: getVolumeValueSizeThemeParams,
    defaultValues: param_definition_1.ParamDefinition.getDefaultValues(exports.VolumeValueSizeThemeParams),
    isApplicable: (ctx) => !!ctx.volume && !volume_1.Volume.Segmentation.get(ctx.volume),
};
