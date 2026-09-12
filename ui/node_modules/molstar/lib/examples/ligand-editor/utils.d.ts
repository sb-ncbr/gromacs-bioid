/**
 * Copyright (c) 2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 */
export declare class SingleTaskQueue {
    private queue;
    run(fn: () => Promise<void>): void;
    private next;
}
