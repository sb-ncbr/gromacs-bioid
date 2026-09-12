/**
 * Copyright (c) 2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 */
export declare class ErrorContext {
    private errors;
    get(tag: string): ReadonlyArray<any>;
    add(tag: string, error: any): void;
    clear(tag: string): void;
}
