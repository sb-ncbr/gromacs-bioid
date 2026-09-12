import React from 'react';
import { ArrayLayoutProps, JsonSchema, JsonFormsCellRendererRegistryEntry, ArrayTranslations } from '@jsonforms/core';
import { WithDeleteDialogSupport } from './DeleteDialog';
export interface EmptyTableProps {
    numColumns: number;
    translations: ArrayTranslations;
}
interface NonEmptyRowProps {
    childPath: string;
    schema: JsonSchema;
    rowIndex: number;
    moveUpCreator: (path: string, position: number) => () => void;
    moveDownCreator: (path: string, position: number) => () => void;
    enableUp: boolean;
    enableDown: boolean;
    showSortButtons: boolean;
    enabled: boolean;
    cells?: JsonFormsCellRendererRegistryEntry[];
    path: string;
    translations: ArrayTranslations;
    disableRemove?: boolean;
}
export declare const NonEmptyRow: React.MemoExoticComponent<({ childPath, schema, rowIndex, openDeleteDialog, moveUpCreator, moveDownCreator, enableUp, enableDown, showSortButtons, enabled, cells, path, translations, disableRemove, }: NonEmptyRowProps & WithDeleteDialogSupport) => React.JSX.Element>;
export declare class MaterialTableControl extends React.Component<ArrayLayoutProps & WithDeleteDialogSupport & {
    translations: ArrayTranslations;
}, any> {
    addItem: (path: string, value: any) => () => void;
    render(): React.JSX.Element;
}
export {};
