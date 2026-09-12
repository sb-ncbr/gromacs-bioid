/**
 * Copyright (c) 2018-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 * @author Ludovic Autin <ludovic.autin@gmail.com>
 */
import { StateTransforms } from '../transforms';
import { DataFormatProvider } from './provider';
export const CoordinatesFormatCategory = 'Coordinates';
export { DcdProvider };
const DcdProvider = DataFormatProvider({
    label: 'DCD',
    description: 'DCD',
    category: CoordinatesFormatCategory,
    binaryExtensions: ['dcd'],
    parse: (plugin, data) => {
        const coordinates = plugin.state.data.build()
            .to(data)
            .apply(StateTransforms.Model.CoordinatesFromDcd);
        return coordinates.commit();
    }
});
export { XtcProvider };
const XtcProvider = DataFormatProvider({
    label: 'XTC',
    description: 'XTC',
    category: CoordinatesFormatCategory,
    binaryExtensions: ['xtc'],
    parse: (plugin, data) => {
        const coordinates = plugin.state.data.build()
            .to(data)
            .apply(StateTransforms.Model.CoordinatesFromXtc);
        return coordinates.commit();
    }
});
export { TrrProvider };
const TrrProvider = DataFormatProvider({
    label: 'TRR',
    description: 'TRR',
    category: CoordinatesFormatCategory,
    binaryExtensions: ['trr'],
    parse: (plugin, data) => {
        const coordinates = plugin.state.data.build()
            .to(data)
            .apply(StateTransforms.Model.CoordinatesFromTrr);
        return coordinates.commit();
    }
});
export { NctrajProvider };
const NctrajProvider = DataFormatProvider({
    label: 'NCTRAJ',
    description: 'NCTRAJ',
    category: CoordinatesFormatCategory,
    binaryExtensions: ['nc', 'nctraj'],
    parse: (plugin, data) => {
        const coordinates = plugin.state.data.build()
            .to(data)
            .apply(StateTransforms.Model.CoordinatesFromNctraj);
        return coordinates.commit();
    }
});
export { LammpsTrajectoryProvider };
const LammpsTrajectoryProvider = DataFormatProvider({
    label: 'LAMMPSTRAJ',
    description: 'LAMMPSTRAJ',
    category: CoordinatesFormatCategory,
    stringExtensions: ['lammpstrj'],
    parse: (plugin, data) => {
        const coordinates = plugin.state.data.build()
            .to(data)
            .apply(StateTransforms.Model.CoordinatesFromLammpstraj);
        return coordinates.commit();
    }
});
export const BuiltInCoordinatesFormats = [
    ['dcd', DcdProvider],
    ['xtc', XtcProvider],
    ['trr', TrrProvider],
    ['nctraj', NctrajProvider],
    ['lammpstrj', LammpsTrajectoryProvider],
];
