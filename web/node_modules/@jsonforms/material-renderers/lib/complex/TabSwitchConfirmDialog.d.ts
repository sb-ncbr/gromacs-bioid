import React from 'react';
export interface TabSwitchConfirmDialogProps {
    open: boolean;
    handleClose: () => void;
    confirm: () => void;
    cancel: () => void;
    id: string;
}
export declare const TabSwitchConfirmDialog: ({ open, handleClose, confirm, cancel, id, }: TabSwitchConfirmDialogProps) => React.JSX.Element;
