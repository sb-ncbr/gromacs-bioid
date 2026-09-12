/**
 * Copyright (c) 2021-24 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 * @author David Sehnal <david.sehnal@gmail.com>
 */
import { CifFrame } from '../../../mol-io/reader/cif';
import { mmCIF_Schema } from '../../../mol-io/reader/cif/schema/mmcif';
import { CustomModelProperty } from '../../../mol-model-props/common/custom-model-property';
import { CustomProperty } from '../../../mol-model-props/common/custom-property';
import { Model, ResidueIndex } from '../../../mol-model/structure/model';
import { QuerySymbolRuntime } from '../../../mol-script/runtime/query/compiler';
import { ParamDefinition, ParamDefinition as PD } from '../../../mol-util/param-definition';
export { QualityAssessment };
interface QualityAssessment {
    local: QualityAssessment.Local[];
    /** id -> metric info */
    localMap: Map<number, QualityAssessment.Local>;
    /** default pLDDT metric */
    pLDDT?: Map<ResidueIndex, number>;
    /** default qmean metric */
    qmean?: Map<ResidueIndex, number>;
    /**
     * @deprecated
     * NOTE: Keeping this around in case someone is using it
     * TODO: Remove in Mol* 5.0
     */
    localMetrics: Map<string, Map<ResidueIndex, number>>;
}
declare namespace QualityAssessment {
    interface Local {
        id: number;
        kind?: 'pLDDT' | 'qmean';
        type: mmCIF_Schema['ma_qa_metric']['type']['T'];
        name: string;
        domain?: [number, number];
        valueRange: [number, number];
        values: Map<ResidueIndex, number>;
    }
    interface Pairwise {
        id: number;
        name: string;
        residueRange: [ResidueIndex, ResidueIndex];
        valueRange: [number, number];
        values: Record<ResidueIndex, Record<ResidueIndex, number | undefined> | undefined>;
    }
    function isApplicable(model?: Model, localMetricName?: 'pLDDT' | 'qmean'): boolean;
    function getLocalOptions(model: Model | undefined, kind: 'pLDDT' | 'qmean'): ParamDefinition.Select<number> | ParamDefinition.Select<undefined>;
    function obtain(ctx: CustomProperty.Context, model: Model, props: QualityAssessmentProps): Promise<CustomProperty.Data<QualityAssessment>>;
    function findModelArchiveCIFPAEMetrics(frame: CifFrame): {
        id: number;
        name: string;
    }[];
    function pairwiseMetricFromModelArchiveCIF(model: Model, frame: CifFrame, metricId: number): Pairwise | undefined;
    const symbols: {
        pLDDT: QuerySymbolRuntime;
        qmean: QuerySymbolRuntime;
    };
}
export declare const QualityAssessmentParams: {};
export type QualityAssessmentParams = typeof QualityAssessmentParams;
export type QualityAssessmentProps = PD.Values<QualityAssessmentParams>;
export declare const QualityAssessmentProvider: CustomModelProperty.Provider<QualityAssessmentParams, QualityAssessment>;
