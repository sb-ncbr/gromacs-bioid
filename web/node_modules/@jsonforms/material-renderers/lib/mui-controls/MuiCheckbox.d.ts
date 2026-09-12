import React from 'react';
import { CellProps, WithClassname } from '@jsonforms/core';
import { InputProps } from '@mui/material';
interface MuiCheckboxInputProps {
    inputProps?: InputProps['inputProps'];
}
export declare const MuiCheckbox: React.NamedExoticComponent<CellProps & WithClassname & MuiCheckboxInputProps>;
export {};
