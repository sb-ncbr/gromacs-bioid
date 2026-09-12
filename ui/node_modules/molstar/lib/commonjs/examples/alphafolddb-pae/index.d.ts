/**
 * Copyright (c) 2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 */
import { Viewer } from '../../apps/viewer/app';
import './index.html';
import '../../mol-plugin-ui/skin/light.scss';
export declare class AlphaFoldPAEExample {
    viewer: Viewer;
    plotContainerId: string;
    init(options: {
        pluginContainerId: string;
        plotContainerId: string;
    }): Promise<this>;
    load(afId: string): Promise<void>;
}
