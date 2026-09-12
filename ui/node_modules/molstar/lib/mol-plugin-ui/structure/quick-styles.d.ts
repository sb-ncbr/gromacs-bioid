/**
 * Copyright (c) 2022-2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 * @author David Sehnal <david.sehnal@gmail.com>
 * @author Adam Midlik <midlik@gmail.com>
 */
import { CollapsableControls, PurePluginUIComponent } from '../base';
import { MagicWandSvg } from '../controls/icons';
export declare class StructureQuickStylesControls extends CollapsableControls {
    defaultState(): {
        isCollapsed: boolean;
        header: string;
        brand: {
            accent: "gray";
            svg: typeof MagicWandSvg;
        };
    };
    renderControls(): import("react/jsx-runtime").JSX.Element;
}
type PresetName = 'default' | 'cartoon' | 'spacefill' | 'surface';
type StyleName = 'default' | 'illustrative';
interface QuickStylesState {
    busy: boolean;
    style: StyleName;
}
export declare class QuickStyles extends PurePluginUIComponent<{}, QuickStylesState> {
    state: QuickStylesState;
    applyRepresentation(preset: PresetName): Promise<void>;
    applyStyle(style: StyleName): Promise<void>;
    render(): import("react/jsx-runtime").JSX.Element;
}
export {};
