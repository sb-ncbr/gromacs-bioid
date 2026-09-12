/**
 * Copyright (c) 2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
import { ParamDefinition as PD } from '../../mol-util/param-definition';
import { Volume } from '../../mol-model/volume/volume';
const Description = 'Assign size based on the given value of a volume cell.';
export const VolumeValueSizeThemeParams = {
    scale: PD.Numeric(1, { min: 0.1, max: 5, step: 0.1 }),
};
export function getVolumeValueSizeThemeParams(ctx) {
    return VolumeValueSizeThemeParams; // TODO return copy
}
export function VolumeValueSizeTheme(ctx, props) {
    if (ctx.volume) {
        const { data } = ctx.volume.grid.cells;
        const isLocation = Volume.Cell.isLocation;
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
export const VolumeValueSizeThemeProvider = {
    name: 'volume-value',
    label: 'Volume Value',
    category: '',
    factory: VolumeValueSizeTheme,
    getParams: getVolumeValueSizeThemeParams,
    defaultValues: PD.getDefaultValues(VolumeValueSizeThemeParams),
    isApplicable: (ctx) => !!ctx.volume && !Volume.Segmentation.get(ctx.volume),
};
