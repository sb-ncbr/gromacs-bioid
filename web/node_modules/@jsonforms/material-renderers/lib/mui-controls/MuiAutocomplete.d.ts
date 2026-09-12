import React, { ReactNode } from 'react';
import { ControlProps, EnumCellProps, EnumOption, WithClassname } from '@jsonforms/core';
import { AutocompleteRenderOptionState, FilterOptionsState } from '@mui/material';
export interface WithOptionLabel {
    getOptionLabel?(option: EnumOption): string;
    renderOption?(props: React.HTMLAttributes<HTMLLIElement>, option: EnumOption, state: AutocompleteRenderOptionState): ReactNode;
    filterOptions?(options: EnumOption[], state: FilterOptionsState<EnumOption>): EnumOption[];
}
export declare const MuiAutocomplete: (props: ControlProps & EnumCellProps & WithClassname & WithOptionLabel) => React.JSX.Element;
