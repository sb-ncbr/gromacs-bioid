/**
 * Copyright (c) 2024-25 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 */
import { Model } from '../../../../mol-model/structure';
import { Color } from '../../../../mol-util/color';
import { QualityAssessment } from '../prop';
export type MAResidueRangeInfo = {
    startOffset: number;
    endOffset: number;
    label: string;
};
declare function drawMetricPNG(model: Model, metric: QualityAssessment.Pairwise, colorRange: [Color, Color], noDataColor: Color): {
    model: Model;
    metric: QualityAssessment.Pairwise;
    chains: MAResidueRangeInfo[];
    colorRange: readonly [string, string];
    png: string;
};
export declare function maDrawPairwiseMetricPNG(model: Model, metric: QualityAssessment.Pairwise): {
    model: Model;
    metric: QualityAssessment.Pairwise;
    chains: MAResidueRangeInfo[];
    colorRange: readonly [string, string];
    png: string;
};
export type MAPairwiseMetricDrawing = ReturnType<typeof drawMetricPNG>;
export {};
