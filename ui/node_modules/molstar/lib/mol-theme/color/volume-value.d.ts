/**
 * Copyright (c) 2021-2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
import { ColorTheme } from '../color';
import { ParamDefinition as PD } from '../../mol-util/param-definition';
import { ThemeDataContext } from '../theme';
export declare const VolumeValueColorThemeParams: {
    colorList: PD.ColorList;
    domain: PD.Mapped<PD.NamedParams<PD.Normalize<{
        symmetric: boolean;
    }>, "auto"> | PD.NamedParams<[number, number], "custom">>;
    isRelative: PD.BooleanParam;
    defaultColor: PD.Color;
};
export type VolumeValueColorThemeParams = typeof VolumeValueColorThemeParams;
export declare function getVolumeValueColorThemeParams(ctx: ThemeDataContext): {
    colorList: PD.ColorList;
    domain: PD.Mapped<PD.NamedParams<PD.Normalize<{
        symmetric: boolean;
    }>, "auto"> | PD.NamedParams<[number, number], "custom">>;
    isRelative: PD.BooleanParam;
    defaultColor: PD.Color;
};
export declare function VolumeValueColorTheme(ctx: ThemeDataContext, props: PD.Values<VolumeValueColorThemeParams>): ColorTheme<VolumeValueColorThemeParams, any>;
export declare const VolumeValueColorThemeProvider: ColorTheme.Provider<VolumeValueColorThemeParams, 'volume-value'>;
