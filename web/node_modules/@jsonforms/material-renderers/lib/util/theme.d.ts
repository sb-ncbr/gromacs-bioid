import { Theme, TextFieldProps, InputBaseProps } from '@mui/material';
export interface JsonFormsTheme extends Theme {
    jsonforms?: {
        input?: {
            delete?: {
                background?: string;
            };
        };
    };
}
export interface WithInputProps {
    label?: string;
}
export interface WithSelectProps {
    multiple?: boolean;
}
export declare const defaultInputVariant: TextFieldProps['variant'];
export declare function useInputVariant(): TextFieldProps['variant'];
export declare function useInputComponent(): React.JSXElementConstructor<InputBaseProps & WithInputProps>;
