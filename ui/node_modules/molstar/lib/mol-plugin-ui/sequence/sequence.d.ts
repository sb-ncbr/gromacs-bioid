/**
 * Copyright (c) 2018-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 * @author David Sehnal <david.sehnal@gmail.com>
 * @author Adam Midlik <midlik@gmail.com>
 */
import * as React from 'react';
import { Subject } from 'rxjs';
import { StructureElement, Unit } from '../../mol-model/structure';
import { Representation } from '../../mol-repr/representation';
import { ButtonsType, ModifiersKeys } from '../../mol-util/input/input-observer';
import { MarkerAction } from '../../mol-util/marker-action';
import { PluginUIComponent } from '../base';
import { SequenceWrapper } from './wrapper';
type SequenceProps = {
    sequenceWrapper: SequenceWrapper.Any;
    sequenceNumberPeriod?: number;
    hideSequenceNumbers?: boolean;
};
export declare class Sequence<P extends SequenceProps> extends PluginUIComponent<P> {
    protected parentDiv: React.RefObject<HTMLDivElement>;
    protected lastMouseOverSeqIdx: number;
    protected highlightQueue: Subject<{
        seqIdx: number;
        buttons: number;
        button: number;
        modifiers: ModifiersKeys;
    }>;
    protected markerColors: {
        selected: string;
        highlighted: string;
        focused: string;
    };
    protected lociHighlightProvider: (loci: Representation.Loci, action: MarkerAction) => void;
    protected lociSelectionProvider: (loci: Representation.Loci, action: MarkerAction) => void;
    protected get sequenceNumberPeriod(): number;
    componentDidMount(): void;
    updateColors(): void;
    updateFocus(loci: StructureElement.Loci | undefined): void;
    componentWillUnmount(): void;
    getLoci(seqIdx: number | undefined): StructureElement.Loci | undefined;
    getSeqIdx(e: React.MouseEvent): number | undefined;
    hover(loci: StructureElement.Loci | undefined, buttons: ButtonsType, button: ButtonsType.Flag, modifiers: ModifiersKeys): void;
    click(loci: StructureElement.Loci | undefined, buttons: ButtonsType, button: ButtonsType.Flag, modifiers: ModifiersKeys): void;
    contextMenu: (e: React.MouseEvent) => void;
    protected mouseDownLoci: StructureElement.Loci | undefined;
    mouseDown: (e: React.MouseEvent) => void;
    mouseUp: (e: React.MouseEvent) => void;
    protected getBackgroundColor(seqIdx: number): string;
    protected getResidueClass(seqIdx: number, label: string): string;
    protected residue(seqIdx: number, label: string): import("react/jsx-runtime").JSX.Element;
    protected getSequenceNumberClass(seqIdx: number, seqNum: string, label: string): string;
    protected location: StructureElement.Location<Unit>;
    protected getSequenceNumber(seqIdx: number): string;
    protected padSeqNum(n: string): string;
    protected getSequenceNumberSpan(seqIdx: number, label: string): import("react/jsx-runtime").JSX.Element;
    protected updateMarker(): void;
    mouseMove: (e: React.MouseEvent) => void;
    mouseLeave: (e: React.MouseEvent) => void;
    render(): import("react/jsx-runtime").JSX.Element;
}
export {};
