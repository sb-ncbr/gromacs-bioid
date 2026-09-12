/**
 * Copyright (c) 2021-25 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 * @author David Sehnal <david.sehnal@gmail.com>
 */
import { ColorTheme } from '../../../../mol-theme/color';
import { ThemeDataContext } from '../../../../mol-theme/theme';
import { ParamDefinition as PD } from '../../../../mol-util/param-definition';
export declare function getQmeanScoreColorThemeParams(ctx: ThemeDataContext): {
    metricId: PD.Select<number> | PD.Select<undefined>;
};
export type QmeanScoreColorThemeParams = ReturnType<typeof getQmeanScoreColorThemeParams>;
export declare function QmeanScoreColorTheme(ctx: ThemeDataContext, props: PD.Values<QmeanScoreColorThemeParams>): ColorTheme<QmeanScoreColorThemeParams>;
export declare const QmeanScoreColorThemeProvider: ColorTheme.Provider<QmeanScoreColorThemeParams, 'qmean-score'>;
