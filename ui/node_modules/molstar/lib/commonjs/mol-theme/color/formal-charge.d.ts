/**
 * Copyright (c) 2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
import type { ColorTheme } from '../color';
import { ParamDefinition as PD } from '../../mol-util/param-definition';
import { ThemeDataContext } from '../theme';
export declare const FormalChargeColorThemeParams: {
    domain: PD.Interval;
    list: PD.ColorList;
};
export type FormalChargeColorThemeParams = typeof FormalChargeColorThemeParams;
export declare function getFormalChargeColorThemeParams(ctx: ThemeDataContext): {
    domain: PD.Interval;
    list: PD.ColorList;
};
export declare function FormalChargeColorTheme(ctx: ThemeDataContext, props: PD.Values<FormalChargeColorThemeParams>): ColorTheme<FormalChargeColorThemeParams>;
export declare const FormalChargeColorThemeProvider: ColorTheme.Provider<FormalChargeColorThemeParams, 'formal-charge'>;
