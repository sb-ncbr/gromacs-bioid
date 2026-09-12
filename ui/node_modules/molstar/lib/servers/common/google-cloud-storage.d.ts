/**
 * Copyright (c) 2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Adam Midlik <midlik@gmail.com>
 */
interface gsCreateReadStreamOptions {
    userProject?: string;
    validation?: 'md5' | 'crc32c' | false | true;
    start?: number;
    end?: number;
    decompress?: boolean;
}
export declare function downloadGs(gsUrl: string, options?: gsCreateReadStreamOptions): Promise<Buffer>;
export {};
