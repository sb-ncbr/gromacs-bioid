import React from 'react';
import { CellProps, WithClassname } from '@jsonforms/core';
import { InputProps } from '@mui/material';
import { WithInputProps } from '../util';
interface MuiTextInputProps {
    muiInputProps?: InputProps['inputProps'];
    inputComponent?: InputProps['inputComponent'];
}
export declare const MuiInputText: React.NamedExoticComponent<CellProps & WithClassname & MuiTextInputProps & WithInputProps>;
export {};
