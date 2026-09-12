/**
 * Copyright (c) 2018-2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
import { Color } from '../mol-util/color';
import { CarbohydrateSymbolColorThemeProvider } from './color/carbohydrate-symbol';
import { UniformColorThemeProvider } from './color/uniform';
import { deepEqual } from '../mol-util';
import { ThemeRegistry } from './theme';
import { ChainIdColorThemeProvider } from './color/chain-id';
import { ElementIndexColorThemeProvider } from './color/element-index';
import { ElementSymbolColorThemeProvider } from './color/element-symbol';
import { MoleculeTypeColorThemeProvider } from './color/molecule-type';
import { PolymerIdColorThemeProvider } from './color/polymer-id';
import { PolymerIndexColorThemeProvider } from './color/polymer-index';
import { ResidueNameColorThemeProvider } from './color/residue-name';
import { SecondaryStructureColorThemeProvider } from './color/secondary-structure';
import { SequenceIdColorThemeProvider } from './color/sequence-id';
import { ShapeGroupColorThemeProvider } from './color/shape-group';
import { UnitIndexColorThemeProvider } from './color/unit-index';
import { UncertaintyColorThemeProvider } from './color/uncertainty';
import { EntitySourceColorThemeProvider } from './color/entity-source';
import { IllustrativeColorThemeProvider } from './color/illustrative';
import { HydrophobicityColorThemeProvider } from './color/hydrophobicity';
import { TrajectoryIndexColorThemeProvider } from './color/trajectory-index';
import { OccupancyColorThemeProvider } from './color/occupancy';
import { OperatorNameColorThemeProvider } from './color/operator-name';
import { OperatorHklColorThemeProvider } from './color/operator-hkl';
import { PartialChargeColorThemeProvider } from './color/partial-charge';
import { AtomIdColorThemeProvider } from './color/atom-id';
import { EntityIdColorThemeProvider } from './color/entity-id';
import { VolumeValueColorThemeProvider } from './color/volume-value';
import { ModelIndexColorThemeProvider } from './color/model-index';
import { StructureIndexColorThemeProvider } from './color/structure-index';
import { VolumeSegmentColorThemeProvider } from './color/volume-segment';
import { ExternalVolumeColorThemeProvider } from './color/external-volume';
import { ColorThemeCategory } from './color/categories';
import { CartoonColorThemeProvider } from './color/cartoon';
import { FormalChargeColorThemeProvider } from './color/formal-charge';
import { ExternalStructureColorThemeProvider } from './color/external-structure';
import { getPrecision } from '../mol-util/number';
import { SortedArray } from '../mol-data/int/sorted-array';
import { normalize } from '../mol-math/interpolate';
export { ColorTheme };
var ColorTheme;
(function (ColorTheme) {
    ColorTheme.Category = ColorThemeCategory;
    function Palette(list, kind, domain, defaultColor) {
        const colors = [];
        const hasOffsets = list.every(c => Array.isArray(c));
        if (hasOffsets) {
            let maxPrecision = 0;
            for (const e of list) {
                if (Array.isArray(e)) {
                    const p = getPrecision(e[1]);
                    if (p > maxPrecision)
                        maxPrecision = p;
                }
            }
            const count = Math.pow(10, maxPrecision);
            const sorted = [...list];
            sorted.sort((a, b) => a[1] - b[1]);
            const src = sorted.map(c => c[0]);
            const values = SortedArray.ofSortedArray(sorted.map(c => c[1]));
            const _off = [];
            for (let i = 0, il = values.length - 1; i < il; ++i) {
                _off.push(values[i] + (values[i + 1] - values[i]) / 2);
            }
            _off.push(values[values.length - 1]);
            const off = SortedArray.ofSortedArray(_off);
            for (let i = 0, il = Math.max(count, list.length); i < il; ++i) {
                const t = normalize(i, 0, count - 1);
                const j = SortedArray.findPredecessorIndex(off, t);
                colors[i] = src[j];
            }
        }
        else {
            for (const e of list) {
                if (Array.isArray(e))
                    colors.push(e[0]);
                else
                    colors.push(e);
            }
        }
        return {
            colors,
            filter: kind === 'set' ? 'nearest' : 'linear',
            domain,
            defaultColor,
        };
    }
    ColorTheme.Palette = Palette;
    ColorTheme.PaletteScale = (1 << 24) - 2; // reserve (1 << 24) - 1 for undefiend values
    ColorTheme.EmptyFactory = () => ColorTheme.Empty;
    const EmptyColor = Color(0xCCCCCC);
    ColorTheme.Empty = {
        factory: ColorTheme.EmptyFactory,
        granularity: 'uniform',
        color: () => EmptyColor,
        props: {}
    };
    function areEqual(themeA, themeB) {
        return themeA.contextHash === themeB.contextHash && themeA.factory === themeB.factory && deepEqual(themeA.props, themeB.props);
    }
    ColorTheme.areEqual = areEqual;
    ColorTheme.EmptyProvider = { name: '', label: '', category: '', factory: ColorTheme.EmptyFactory, getParams: () => ({}), defaultValues: {}, isApplicable: () => true };
    function createRegistry() {
        return new ThemeRegistry(ColorTheme.BuiltIn, ColorTheme.EmptyProvider);
    }
    ColorTheme.createRegistry = createRegistry;
    ColorTheme.BuiltIn = {
        'atom-id': AtomIdColorThemeProvider,
        'carbohydrate-symbol': CarbohydrateSymbolColorThemeProvider,
        'cartoon': CartoonColorThemeProvider,
        'chain-id': ChainIdColorThemeProvider,
        'element-index': ElementIndexColorThemeProvider,
        'element-symbol': ElementSymbolColorThemeProvider,
        'entity-id': EntityIdColorThemeProvider,
        'entity-source': EntitySourceColorThemeProvider,
        'external-structure': ExternalStructureColorThemeProvider,
        'external-volume': ExternalVolumeColorThemeProvider,
        'formal-charge': FormalChargeColorThemeProvider,
        'hydrophobicity': HydrophobicityColorThemeProvider,
        'illustrative': IllustrativeColorThemeProvider,
        'model-index': ModelIndexColorThemeProvider,
        'molecule-type': MoleculeTypeColorThemeProvider,
        'occupancy': OccupancyColorThemeProvider,
        'operator-hkl': OperatorHklColorThemeProvider,
        'operator-name': OperatorNameColorThemeProvider,
        'partial-charge': PartialChargeColorThemeProvider,
        'polymer-id': PolymerIdColorThemeProvider,
        'polymer-index': PolymerIndexColorThemeProvider,
        'residue-name': ResidueNameColorThemeProvider,
        'secondary-structure': SecondaryStructureColorThemeProvider,
        'sequence-id': SequenceIdColorThemeProvider,
        'shape-group': ShapeGroupColorThemeProvider,
        'structure-index': StructureIndexColorThemeProvider,
        'trajectory-index': TrajectoryIndexColorThemeProvider,
        'uncertainty': UncertaintyColorThemeProvider,
        'unit-index': UnitIndexColorThemeProvider,
        'uniform': UniformColorThemeProvider,
        'volume-segment': VolumeSegmentColorThemeProvider,
        'volume-value': VolumeValueColorThemeProvider,
    };
})(ColorTheme || (ColorTheme = {}));
export function ColorThemeProvider(p) { return p; }
