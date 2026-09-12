import React from 'react';
import { CellProps, WithClassname } from '@jsonforms/core';
import { InputProps } from '@mui/material';
interface MuiToggleInputProps {
    inputProps?: InputProps['inputProps'];
}
export declare const MuiToggle: React.NamedExoticComponent<CellProps & WithClassname & MuiToggleInputProps>;
export {};
