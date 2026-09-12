/**
 * Copyright (c) 2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
import type { SizeTheme } from '../size';
import { ParamDefinition as PD } from '../../mol-util/param-definition';
import { ThemeDataContext } from '../../mol-theme/theme';
export declare const VolumeValueSizeThemeParams: {
    scale: PD.Numeric;
};
export type VolumeValueSizeThemeParams = typeof VolumeValueSizeThemeParams;
export declare function getVolumeValueSizeThemeParams(ctx: ThemeDataContext): {
    scale: PD.Numeric;
};
export declare function VolumeValueSizeTheme(ctx: ThemeDataContext, props: PD.Values<VolumeValueSizeThemeParams>): SizeTheme<VolumeValueSizeThemeParams>;
export declare const VolumeValueSizeThemeProvider: SizeTheme.Provider<VolumeValueSizeThemeParams, 'volume-value'>;
